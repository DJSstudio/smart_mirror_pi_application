// Gallery video card — larger, cleaner retail style.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    property string videoId: ""
    property string title: ""
    property string durationLabel: "--:--"
    property string thumbnailUrl: ""
    property string createdLabel: ""
    property bool selected: false
    property int selectionIndex: -1

    signal tapped()
    signal checkboxTapped()

    width: 200
    height: 270
    radius: 16
    color: "#FFFFFF"
    border.width: root.selected ? 2 : 1
    border.color: root.selected ? "#1C1917" : "#E8E2DC"
    clip: true

    scale: _bodyMa.containsMouse ? 1.02 : 1.0
    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutQuad } }

    // ── Thumbnail ────────────────────────────────────────────────────
    Item {
        id: _thumbArea
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: parent.height * 0.62
        clip: true

        // Background fill
        Rectangle {
            anchors.fill: parent
            color: "#F0EBE5"
        }

        Image {
            anchors.fill: parent
            fillMode: Image.PreserveAspectCrop
            source: root.thumbnailUrl
            visible: root.thumbnailUrl.length > 0
        }

        // Placeholder icon
        Text {
            anchors.centerIn: parent
            visible: root.thumbnailUrl.length === 0
            text: "▶"
            font.pixelSize: 32
            color: "#B0A89E"
        }

        // Gradient vignette at bottom
        Rectangle {
            anchors.fill: parent
            gradient: Gradient {
                GradientStop { position: 0.55; color: "transparent" }
                GradientStop { position: 1.0;  color: "#55000000" }
            }
        }

        // Duration badge
        Rectangle {
            anchors { left: parent.left; bottom: parent.bottom; margins: 10 }
            radius: 6
            color: "#CC000000"
            width: _durTxt.implicitWidth + 12
            height: 22

            Text {
                id: _durTxt
                anchors.centerIn: parent
                text: root.durationLabel
                font.pixelSize: 11
                font.weight: Font.DemiBold
                color: "#FFFFFF"
            }
        }
    }

    // ── Text info ────────────────────────────────────────────────────
    ColumnLayout {
        anchors {
            top: _thumbArea.bottom; topMargin: 10
            left: parent.left; leftMargin: 12
            right: parent.right; rightMargin: 12
            bottom: parent.bottom; bottomMargin: 10
        }
        spacing: 3

        Text {
            Layout.fillWidth: true
            text: root.title
            font.pixelSize: 14
            font.weight: Font.DemiBold
            color: "#1C1917"
            elide: Text.ElideRight
        }

        Text {
            Layout.fillWidth: true
            text: root.createdLabel
            font.pixelSize: 12
            color: "#A09890"
            elide: Text.ElideRight
        }
    }

    // ── Tap body → play ──────────────────────────────────────────────
    MouseArea {
        id: _bodyMa
        anchors.fill: parent
        hoverEnabled: true
        onClicked: root.tapped()
    }

    // ── Selection circle (top-right) ─────────────────────────────────
    Rectangle {
        anchors { top: parent.top; right: parent.right; margins: 10 }
        width: 32; height: 32; radius: 999
        color: root.selected ? "#1C1917" : "transparent"
        border.width: root.selected ? 0 : 2
        border.color: "#FFFFFFCC"

        // Outer shadow ring — keeps outline visible on any thumbnail
        Rectangle {
            visible: !root.selected
            anchors.centerIn: parent
            width: parent.width + 2; height: parent.height + 2
            radius: 999; color: "transparent"
            border.width: 1; border.color: "#44000000"
            z: -1
        }

        Text {
            anchors.centerIn: parent
            visible: root.selected
            text: root.selectionIndex > 0 ? root.selectionIndex.toString() : "✓"
            font.pixelSize: 14; font.weight: Font.Bold
            color: "#FFFFFF"
        }

        MouseArea {
            anchors { fill: parent; margins: -6 }
            onClicked: (mouse) => { mouse.accepted = true; root.checkboxTapped() }
        }
    }
}
