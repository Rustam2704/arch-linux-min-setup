#include "phases.h"
#include <QGenericPlugin>
#include <QGuiApplication>
#include <QTimer>

class ScrollPhasesPlugin final : public QGenericPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QGenericPluginFactoryInterface_iid FILE "plugin.json")
public:
    QObject *create(const QString &key, const QString &) override {
        if (key != "scrollphases") return nullptr;
        auto *owner = new QObject;
        if (QString::fromLatin1(qVersion()) != QStringLiteral(QT_VERSION_STR)) {
            qWarning("scrollphases: rebuild for this Qt version; leaving input unchanged");
            return owner;
        }
        // QGuiApplication is still being constructed when generic plugins load.
        QTimer::singleShot(0, owner, [owner] {
            if (QGuiApplication::platformName() == "xcb")
                new ScrollPhases(owner);
        });
        return owner;
    }
};
#include "plugin.moc"
