import QtQuick
import QtQuick.Controls

Button {
    id: root

    property color backgroundColor: "#f2e5d8"
    property color foregroundColor: "#4c4036"
    property color borderColor: "#d6c3b1"

    implicitHeight: 48
    implicitWidth: Math.max(160, contentItem.implicitWidth + 28)

    background: Rectangle {
        radius: 18
        color: root.enabled ? root.backgroundColor : "#e7ddd3"
        border.width: 1
        border.color: root.borderColor
        opacity: root.down ? 0.88 : 1.0
    }

    contentItem: Text {
        text: root.text
        font.family: "Noto Serif"
        font.pixelSize: 16
        font.weight: Font.DemiBold
        color: root.enabled ? root.foregroundColor : "#9d9084"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
}
