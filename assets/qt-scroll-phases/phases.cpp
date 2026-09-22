#include "phases.h"
#include <QCoreApplication>
#include <QGuiApplication>
#include <QSocketNotifier>
#include <QWheelEvent>
#include <qpa/qwindowsysteminterface.h>
#include <qpa/qwindowsysteminterface_p.h>
#include <libevdev/libevdev.h>
#include <libudev.h>
#include <fcntl.h>
#include <unistd.h>
#include <algorithm>
#include <cerrno>

void ContactHistory::update(int fingers, quint32 time) {
    const bool now = fingers == 2;
    if (now == two) return;
    two = now;
    if (now) {
        spans.push_back({++serial, time});
        if (spans.size() > 64) spans.pop_front();
    } else if (!spans.empty()) {
        spans.back().end = time;
        spans.back().ended = true;
    }
}

const ContactHistory::Span *ContactHistory::at(quint32 time) const {
    for (auto it = spans.rbegin(); it != spans.rend(); ++it) {
        // X timestamps wrap at 32 bits; signed differences handle that wrap.
        if (qint32(time - it->begin) >= 0 &&
            (!it->ended || qint32(time - it->end) <= 0)) return &*it;
    }
    return nullptr;
}

ScrollPhases::Pad::~Pad() {
    delete notifier;
    if (evdev) libevdev_free(evdev);
    if (fd >= 0) close(fd);
}

ScrollPhases::ScrollPhases(QObject *parent, bool hardware) : QObject(parent) {
    endTimer.setSingleShot(true);
    // This only drains the final X event after a *physical* release. It is not
    // an inactivity timeout: pausing with fingers down never ends a gesture.
    endTimer.setInterval(25);
    connect(&endTimer, &QTimer::timeout, this, &ScrollPhases::finish);
    qApp->installEventFilter(this);
    if (!hardware) return;
    context = udev_new();
    if (!context) return;
    monitor = udev_monitor_new_from_netlink(context, "udev");
    if (monitor) {
        udev_monitor_filter_add_match_subsystem_devtype(monitor, "input", nullptr);
        udev_monitor_enable_receiving(monitor);
        monitorNotifier = new QSocketNotifier(udev_monitor_get_fd(monitor), QSocketNotifier::Read, this);
        connect(monitorNotifier, &QSocketNotifier::activated, this, [this] {
            while (auto *dev = udev_monitor_receive_device(monitor)) {
                const char *path = udev_device_get_devnode(dev);
                const char *action = udev_device_get_action(dev);
                const char *touchpad = udev_device_get_property_value(dev, "ID_INPUT_TOUCHPAD");
                if (path && action && QByteArray(action) == "remove") {
                    for (auto &p : pads) if (p->path == path && activePad == p->name) finish();
                    pads.erase(std::remove_if(pads.begin(), pads.end(), [path](const auto &p) {
                        return p->path == path;
                    }), pads.end());
                } else if (path && touchpad && QByteArray(touchpad) == "1") {
                    addPad(path);
                }
                udev_device_unref(dev);
            }
        });
    }
    auto *enumerator = udev_enumerate_new(context);
    udev_enumerate_add_match_subsystem(enumerator, "input");
    udev_enumerate_add_match_property(enumerator, "ID_INPUT_TOUCHPAD", "1");
    udev_enumerate_scan_devices(enumerator);
    udev_list_entry *entry;
    udev_list_entry_foreach(entry, udev_enumerate_get_list_entry(enumerator)) {
        auto *dev = udev_device_new_from_syspath(context, udev_list_entry_get_name(entry));
        if (const char *path = udev_device_get_devnode(dev)) addPad(path);
        udev_device_unref(dev);
    }
    udev_enumerate_unref(enumerator);
}

ScrollPhases::~ScrollPhases() {
    delete monitorNotifier;
    pads.clear();
    if (monitor) udev_monitor_unref(monitor);
    if (context) udev_unref(context);
}

void ScrollPhases::addPad(const char *path) {
    if (!QByteArray(path).startsWith("/dev/input/event")) return;
    for (auto &pad : pads) if (pad->path == path) return;
    auto pad = std::make_unique<Pad>();
    pad->fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
    if (pad->fd < 0 || libevdev_new_from_fd(pad->fd, &pad->evdev) < 0) return;
    // Do not guess boundaries on unsupported devices or clocks.
    if (!libevdev_has_event_code(pad->evdev, EV_KEY, BTN_TOOL_DOUBLETAP) ||
        libevdev_set_clock_id(pad->evdev, CLOCK_MONOTONIC) < 0) return;
    pad->path = path;
    pad->name = QString::fromUtf8(libevdev_get_name(pad->evdev));
    pad->notifier = new QSocketNotifier(pad->fd, QSocketNotifier::Read, this);
    auto *p = pad.get();
    connect(p->notifier, &QSocketNotifier::activated, this, [this, p] { readPad(*p); });
    pads.push_back(std::move(pad));
}

ScrollPhases::Pad *ScrollPhases::findPad(const QString &name) {
    for (auto &p : pads) if (p->name == name) return p.get();
    return nullptr;
}

void ScrollPhases::contacts(const QString &name, int fingers, quint32 timestamp) {
    auto *pad = findPad(name);
    if (!pad) {
        auto p = std::make_unique<Pad>();
        p->name = name;
        pad = p.get();
        pads.push_back(std::move(p));
    }
    const bool wasTwo = pad->history.two;
    pad->history.update(fingers, timestamp);
    if (activePad == name && activeSpan && wasTwo && !pad->history.two) endTimer.start();
}

void ScrollPhases::readPad(Pad &pad) {
    input_event event;
    int status;
    unsigned flags = LIBEVDEV_READ_FLAG_NORMAL;
    while ((status = libevdev_next_event(pad.evdev, flags, &event)) >= 0) {
        if (status == LIBEVDEV_READ_STATUS_SYNC) {
            // Recover dropped frames with libevdev's state synchronization.
            flags = LIBEVDEV_READ_FLAG_SYNC;
        }
        if (event.type == EV_SYN && event.code == SYN_REPORT) {
            const bool two = libevdev_get_event_value(pad.evdev, EV_KEY, BTN_TOOL_DOUBLETAP);
            contacts(pad.name, two ? 2 : 0, quint32(event.time.tv_sec * 1000ULL + event.time.tv_usec / 1000));
        }
    }
    if (flags == LIBEVDEV_READ_FLAG_SYNC && status == -EAGAIN) {
        readPad(pad);
    } else if (status != -EAGAIN) {
        pad.notifier->setEnabled(false);
        if (activePad == pad.name) finish();
    }
}

bool ScrollPhases::eventFilter(QObject *object, QEvent *event) {
    if (event->type() != QEvent::Wheel) return false;
    auto *window = qobject_cast<QWindow *>(object);
    if (!window) return false;
    auto *wheel = static_cast<QWheelEvent *>(event);
    if (wheel->phase() != Qt::NoScrollPhase) return false;
    if (wheel->deviceType() != QInputDevice::DeviceType::TouchPad) {
        // Release Qt's implicit wheel-widget grab before an unrelated mouse
        // wheel event, otherwise it could be routed to the old widget.
        if (activeSpan) finish();
        return false;
    }
    auto *pad = findPad(wheel->device()->name());
    if (!pad) return false; // Preserve normal scrolling if monitoring is unavailable.
    if (pad->evdev) readPad(*pad); // Native X delivery can precede our notifier.
    const auto *span = pad->history.at(quint32(wheel->timestamp()));
    if (!span || (closedPad == pad->name && closedSpan == span->id)) return false;
    const bool fresh = !activeSpan || activePad != pad->name || activeSpan != span->id || target != window;
    if (fresh && activeSpan) finish();
    target = window;
    device = wheel->pointingDevice();
    activePad = pad->name;
    activeSpan = span->id;
    local = wheel->position();
    global = wheel->globalPosition();
    modifiers = wheel->modifiers();
    source = wheel->source();
    inverted = wheel->inverted();
    lastTimestamp = quint32(wheel->timestamp());
    if (fresh) emitWheel(Qt::ScrollBegin);
    emitWheel(Qt::ScrollUpdate, wheel->pixelDelta(), wheel->angleDelta());
    if (span->ended) endTimer.start();
    else endTimer.stop();
    return true;
}

void ScrollPhases::emitWheel(Qt::ScrollPhase phase, QPoint pixels, QPoint angle) {
    if (!target || !device) return;
    // Re-enter through QPA so widget propagation remains spontaneous. Sending
    // a synthetic QWidget event would break scrolling over child widgets.
    // The public QPA wheel helper splits a zero-delta boundary into two events
    // for Qt 4 compatibility, and re-scales logical coordinates on HiDPI.
    // Deliver one already-translated QPA event instead.
    QWindowSystemInterfacePrivate::WheelEvent event(target, lastTimestamp,
        local, global, pixels, angle, 0, Qt::Horizontal,
        modifiers, phase, source, inverted, device);
    QWindowSystemEventHandler handler;
    handler.sendEvent(&event);
}

void ScrollPhases::finish() {
    endTimer.stop();
    if (activeSpan) {
        emitWheel(Qt::ScrollEnd);
        closedPad = activePad;
        closedSpan = activeSpan;
    }
    activeSpan = 0;
    target.clear();
    device.clear();
}
