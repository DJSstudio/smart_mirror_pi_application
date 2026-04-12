// Pre-recording countdown overlay (3… 2… 1…)
import QtQuick

Item {
    id: root
    property int count: 0
    visible: count > 0

    Rectangle {
        anchors.fill: parent
        color: "#cc0a0907"
        radius: 20
    }

    Text {
        id: countText
        anchors.centerIn: parent
        text: root.count > 0 ? root.count.toString() : ""
        font.family: "Noto Serif, Georgia, serif"
        font.pixelSize: 120
        font.weight: Font.Bold
        color: "#fff8f4"
        opacity: 0.92

        SequentialAnimation on scale {
            running: root.count > 0
            loops: Animation.Infinite
            NumberAnimation { to: 1.15; duration: 300; easing.type: Easing.OutQuad }
            NumberAnimation { to: 1.0;  duration: 700; easing.type: Easing.InQuad }
        }
    }

    Text {
        anchors {
            horizontalCenter: parent.horizontalCenter
            top: countText.bottom
            topMargin: 16
        }
        text: "Get ready…"
        font.pixelSize: 18
        color: "#d0c8c0"
    }
}
