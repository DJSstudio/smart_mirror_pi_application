// Gallery video card — thumbnail, title, duration badge, selection overlay.
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
    property int selectionIndex: -1  // 1 or 2 when selected

    signal tapped()
    signal longPressed()

    width: 160
    height: 220
    radius: 16
    color: root.selected ? "#e2d8cf" : "#f4ede8"
    border.width: root.selected ? 2 : 1
    border.color: root.selected ? "#a09080" : "#d6cdc5"
    clip: true

    // Thumbnail
    Image {
        id: thumb
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: parent.height * 0.62
        fillMode: Image.PreserveAspectCrop
        source: root.thumbnailUrl
        visible: root.thumbnailUrl.length > 0

        Rectangle {
            anchors.fill: parent
            color: "transparent"
            // Subtle vignette at bottom
            gradient: Gradient {
                GradientStop { position: 0.6; color: "transparent" }
                GradientStop { position: 1.0; color: "#44000000" }
            }
        }
    }

    // Placeholder when no thumbnail
    Rectangle {
        anchors { top: parent.top; left: parent.left; right: parent.right }
        height: parent.height * 0.62
        visible: root.thumbnailUrl.length === 0
        color: "#e2dbd5"

        Text {
            anchors.centerIn: parent
            text: "▶"
            font.pixelSize: 28
            color: "#a09590"
        }
    }

    // Duration badge
    Rectangle {
        anchors { right: parent.right; bottom: parent.top; rightMargin: 8 }
        anchors.bottomMargin: -(parent.height * 0.62) + 8
        radius: 999
        color: "#cc0a0804"
        width: durationText.implicitWidth + 12
        height: 22

        Text {
            id: durationText
            anchors.centerIn: parent
            text: root.durationLabel
            font.pixelSize: 11
            font.weight: Font.DemiBold
            color: "#f5ede8"
        }
    }

    // Title + date
    ColumnLayout {
        anchors {
            left: parent.left; right: parent.right
            top: parent.top; topMargin: parent.height * 0.62 + 8
            bottom: parent.bottom; bottomMargin: 8
        }
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        spacing: 2

        Text {
            Layout.fillWidth: true
            text: root.title
            font.family: "Noto Serif, Georgia, serif"
            font.pixelSize: 13
            font.weight: Font.DemiBold
            color: "#3c3530"
            elide: Text.ElideRight
        }

        Text {
            Layout.fillWidth: true
            text: root.createdLabel
            font.pixelSize: 11
            color: "#9d9590"
            elide: Text.ElideRight
        }
    }

    // Selection badge
    Rectangle {
        visible: root.selected
        anchors { top: parent.top; right: parent.right; topMargin: 8; rightMargin: 8 }
        width: 26; height: 26
        radius: 999
        color: "#7a6a5a"

        Text {
            anchors.centerIn: parent
            text: root.selectionIndex > 0 ? root.selectionIndex.toString() : "✓"
            font.pixelSize: 13
            font.weight: Font.Bold
            color: "#fff8f4"
        }
    }

    // Touch / mouse handling
    MouseArea {
        anchors.fill: parent
        pressAndHoldInterval: 600
        onClicked: root.tapped()
        onPressAndHold: root.longPressed()
    }
}
