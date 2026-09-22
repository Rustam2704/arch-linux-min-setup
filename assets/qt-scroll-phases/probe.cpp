#include <QGuiApplication>
#include <QDebug>
#include <QInputDevice>
#include <QTimer>
#include <unistd.h>

int main(int argc, char **argv) {
    QGuiApplication app(argc, argv);
    QTimer::singleShot(100, &app, [&] {
        qInfo() << "PID" << getpid() << "Qt" << qVersion();
        for (auto *device : QInputDevice::devices()) qInfo() << device;
        if (!app.arguments().contains("--wait")) app.quit();
    });
    QTimer::singleShot(15000, &app, &QCoreApplication::quit);
    return app.exec();
}
