#include "phases.h"
#include <QApplication>
#include <QLabel>
#include <QScrollArea>
#include <QScrollBar>
#include <QTest>
#include <QWheelEvent>
#include <qpa/qwindowsysteminterface.h>

class Receiver : public QWidget {
public:
    QList<Qt::ScrollPhase> phases;
    QPoint sum;
    bool allSpontaneous = true;
    void wheelEvent(QWheelEvent *e) override {
        phases << e->phase();
        sum += e->angleDelta();
        allSpontaneous &= e->spontaneous();
        e->accept();
    }
};

class Tests : public QObject {
    Q_OBJECT
    QPointingDevice pad{"test-pad", 54321, QInputDevice::DeviceType::TouchPad,
        QPointingDevice::PointerType::Finger,
        QInputDevice::Capability::Position | QInputDevice::Capability::Scroll, 5, 3};
    QPointingDevice mouse{"test-mouse", 54322, QInputDevice::DeviceType::Mouse,
        QPointingDevice::PointerType::Generic,
        QInputDevice::Capability::Position | QInputDevice::Capability::Scroll, 1, 3};
    void wheel(QWidget &widget, quint32 time, QPoint angle,
               const QPointingDevice *device = nullptr,
               Qt::ScrollPhase phase = Qt::NoScrollPhase, QPointF pos = {30, 30}) {
        QWindowSystemInterface::handleWheelEvent(widget.windowHandle(), time,
            device ? device : &pad, pos, widget.mapToGlobal(pos.toPoint()), {}, angle,
            Qt::NoModifier, phase);
        QCoreApplication::processEvents();
        QCoreApplication::processEvents();
    }
private slots:
    void initTestCase() {
        QWindowSystemInterface::registerInputDevice(&mouse);
        QWindowSystemInterface::registerInputDevice(&pad);
    }
    void onePhysicalGestureDespitePause() {
        ScrollPhases bridge(nullptr, false);
        Receiver view; view.resize(200, 200); view.show();
        QCoreApplication::processEvents();
        bridge.contacts(pad.name(), 2, 1000);
        for (int i=0; i<20; ++i) wheel(view, 1010+i, {-12, 0});
        QTest::qWait(300); // A pause must not commit a photo navigation.
        QCOMPARE(view.phases.count(Qt::ScrollEnd), 0);
        wheel(view, 1400, {-12, 0});
        bridge.contacts(pad.name(), 0, 1410);
        QTest::qWait(50);
        QCOMPARE(view.phases.count(Qt::ScrollBegin), 1);
        QCOMPARE(view.phases.count(Qt::ScrollEnd), 1);
        QCOMPARE(view.sum, QPoint(-252, 0));
        QVERIFY(view.allSpontaneous);
    }
    void rapidDistinctGesturesAndDelayedXDelivery() {
        ScrollPhases bridge(nullptr, false);
        Receiver view; view.resize(200, 200); view.show();
        QCoreApplication::processEvents();
        // Contact notifications may arrive before X delivers the final delta.
        bridge.contacts(pad.name(), 2, 2000);
        bridge.contacts(pad.name(), 0, 2030);
        bridge.contacts(pad.name(), 2, 2040);
        wheel(view, 2020, {-120, 0});
        wheel(view, 2050, {120, 0});
        bridge.contacts(pad.name(), 0, 2060);
        QTest::qWait(50);
        QCOMPARE(view.phases, QList<Qt::ScrollPhase>({Qt::ScrollBegin, Qt::ScrollUpdate,
            Qt::ScrollEnd, Qt::ScrollBegin, Qt::ScrollUpdate, Qt::ScrollEnd}));
    }
    void mouseUnmonitoredAndAlreadyPhasedInputUnchanged() {
        ScrollPhases bridge(nullptr, false);
        Receiver view; view.resize(200, 200); view.show();
        QCoreApplication::processEvents();
        wheel(view, 3000, {0,-120}, &mouse);
        wheel(view, 3010, {0,-120}); // No touchpad permissions/contact history.
        bridge.contacts(pad.name(), 2, 3020);
        wheel(view, 3030, {0,-120}, &pad, Qt::ScrollUpdate);
        QCOMPARE(view.phases, QList<Qt::ScrollPhase>({Qt::NoScrollPhase,
            Qt::NoScrollPhase, Qt::ScrollUpdate}));
        QCOMPARE(view.sum, QPoint(0,-360));
    }
    void scrollAreaStillScrollsOverChildWidgets() {
        ScrollPhases bridge(nullptr, false);
        QScrollArea area;
        auto *label = new QLabel(QString("Long content\n").repeated(300));
        label->setMinimumSize(1000,10000);
        area.setWidget(label); area.resize(300,300); area.show();
        QCoreApplication::processEvents();
        bridge.contacts(pad.name(), 2, 4000);
        wheel(area, 4010, {0,-120});
        QVERIFY(area.verticalScrollBar()->value() > 0);
        QCOMPARE(area.horizontalScrollBar()->value(), 0);
        wheel(area, 4020, {-120,0});
        QVERIFY(area.horizontalScrollBar()->value() > 0);
        bridge.contacts(pad.name(), 0, 4030);
        QTest::qWait(50);
    }
    void timestampWrap() {
        ContactHistory history;
        history.update(2, 0xfffffff0);
        history.update(0, 20);
        QVERIFY(history.at(0xfffffff8));
        QVERIFY(history.at(10));
        QVERIFY(!history.at(30));
    }
    void mouseInterruptsTouchpadWithoutStealingItsTarget() {
        ScrollPhases bridge(nullptr, false);
        Receiver first, second;
        first.resize(200,200); second.resize(200,200);
        first.show(); second.show(); QCoreApplication::processEvents();
        bridge.contacts(pad.name(), 2, 4500);
        wheel(first, 4510, {-120,0});
        wheel(second, 4520, {0,-120}, &mouse);
        QCOMPARE(first.phases.count(Qt::ScrollEnd), 1);
        QCOMPARE(first.sum, QPoint(-120,0));
        QCOMPARE(second.sum, QPoint(0,-120));
        QCOMPARE(second.phases, QList<Qt::ScrollPhase>({Qt::NoScrollPhase}));
    }
    void windowClosedDuringGesture() {
        ScrollPhases bridge(nullptr, false);
        auto view = std::make_unique<Receiver>();
        view->resize(200,200); view->show(); QCoreApplication::processEvents();
        bridge.contacts(pad.name(), 2, 5000);
        wheel(*view, 5010, {-120,0});
        view.reset();
        bridge.contacts(pad.name(), 0, 5020);
        QTest::qWait(50); // Must not redirect the release to another window.
    }
};

QTEST_MAIN(Tests)
#include "test_phases.moc"
