// Standard button — clean bold palette for retail kiosk.
import QtQuick
import QtQuick.Controls

Button {
    id: root

    // Style variants
    property string variant: "primary"   // "primary" | "secondary" | "danger" | "ghost"

    property color _bg: variant === "danger"    ? "#8B2E2E"
                      : variant === "secondary"  ? "#EDE8E3"
                      : variant === "ghost"      ? "transparent"
                      :                            "#1C1917"

    property color _fg: variant === "danger"    ? "#FFFFFF"
                      : variant === "secondary"  ? "#1C1917"
                      : variant === "ghost"      ? "#6B6560"
                      :                            "#FFFFFF"

    property color _border: variant === "secondary" ? "#D8D0C8"
                           : variant === "ghost"     ? "#D8D0C8"
                           :                           "transparent"

    implicitHeight: 54
    implicitWidth: Math.max(140, contentItem.implicitWidth + 40)

    background: Rectangle {
        radius: 999
        color: root.enabled ? root._bg : (root.variant === "primary" ? "#9A9490" : "#EDE8E3")
        border.width: root._border === "transparent" ? 0 : 1
        border.color: root.enabled ? root._border : "#D8D0C8"
        opacity: root.down ? 0.78 : 1.0

        Behavior on color   { ColorAnimation  { duration: 100 } }
        Behavior on opacity { NumberAnimation { duration: 80  } }
    }

    contentItem: Text {
        text: root.text
        font.pixelSize: 15
        font.weight: Font.DemiBold
        color: root.enabled ? root._fg : "#A09890"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
