#pragma once
#include <QObject>
#include <QPointer>
#include <QPointF>
#include <QTimer>
#include <QWindow>
#include <QPointingDevice>
#include <deque>
#include <memory>
#include <vector>

struct udev;
struct udev_monitor;
struct libevdev;
class QSocketNotifier;

// The input side observes only touchpad contact boundaries, never grabs input
// and never emits keys. Xorg/Qt remain responsible for motion and scrolling.
struct ContactHistory {
    struct Span { quint64 id; quint32 begin; quint32 end = 0; bool ended = false; };
    std::deque<Span> spans;
    quint64 serial = 0;
    bool two = false;
    void update(int fingers, quint32 time);
    const Span *at(quint32 time) const;
};

class ScrollPhases final : public QObject {
public:
    explicit ScrollPhases(QObject *parent = nullptr, bool monitorHardware = true);
    ~ScrollPhases() override;
    // Also used by the regression harness to supply physical contact frames.
    void contacts(const QString &device, int fingers, quint32 timestamp);
protected:
    bool eventFilter(QObject *object, QEvent *event) override;
private:
    struct Pad {
        QString path, name;
        int fd = -1;
        libevdev *evdev = nullptr;
        QSocketNotifier *notifier = nullptr;
        ContactHistory history;
        ~Pad();
    };
    std::vector<std::unique_ptr<Pad>> pads;
    udev *context = nullptr;
    udev_monitor *monitor = nullptr;
    QSocketNotifier *monitorNotifier = nullptr;
    QTimer endTimer;
    QPointer<QWindow> target;
    QPointer<const QPointingDevice> device;
    QString activePad;
    quint64 activeSpan = 0, closedSpan = 0;
    QString closedPad;
    QPointF local, global;
    Qt::KeyboardModifiers modifiers = Qt::NoModifier;
    Qt::MouseEventSource source = Qt::MouseEventNotSynthesized;
    bool inverted = false;
    quint32 lastTimestamp = 0;
    void addPad(const char *path);
    void readPad(Pad &pad);
    Pad *findPad(const QString &name);
    void finish();
    void emitWheel(Qt::ScrollPhase phase, QPoint pixels = {}, QPoint angle = {});
};
