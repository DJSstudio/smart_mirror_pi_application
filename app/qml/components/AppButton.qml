// Standard button — pill-shaped, warm neutral palette.
import QtQuick
import QtQuick.Controls

Button {
    id: root

    // Style variants
    property string variant: "primary"   // "primary" | "secondary" | "danger" | "ghost"

    property color _bg: variant === "danger"    ? "#9e4b4b"
                      : variant === "secondary"  ? "#ece4dd"
                      : variant === "ghost"      ? "transparent"
                      :                            "#d6c9bd"

    property color _fg: variant === "danger"   ? "#fff7f5"
                      : variant === "ghost"     ? "#6b6661"
                      :                           "#3c3530"

    property color _border: variant === "danger"    ? "#8a3a3a"
                           : variant === "ghost"     ? "#c9bfb7"
                           :                           "#c4b8ac"

    implicitHeight: 48
    implicitWidth: Math.max(160, contentItem.implicitWidth + 32)

    background: Rectangle {
        radius: 999
        color: root.enabled ? root._bg : "#e2dbd5"
        border.width: 1
        border.color: root.enabled ? root._border : "#cfc8c1"
        opacity: root.down ? 0.82 : 1.0

        Behavior on opacity { NumberAnimation { duration: 80 } }
    }

    contentItem: Text {
        text: root.text
        font.family: "Noto Serif, Georgia, serif"
        font.pixelSize: 15
        font.weight: Font.DemiBold
        color: root.enabled ? root._fg : "#a09590"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
}
