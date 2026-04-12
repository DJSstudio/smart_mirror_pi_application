// Gallery video card — thumbnail, title, duration badge, selection checkbox.
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
    signal checkboxTapped()

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

    // Card body tap → play.  Declared before the checkbox so the checkbox
    // (higher z-order, declared later) can intercept its own taps.
    MouseArea {
        anchors.fill: parent
        onClicked: root.tapped()
    }

    // Checkbox — always visible in the top-right corner of the thumbnail.
    // Declared after the body MouseArea so it sits on top and captures
    // taps independently from the card body.
    Rectangle {
        id: checkbox
        anchors { top: parent.top; right: parent.right; topMargin: 8; rightMargin: 8 }
        width: 30; height: 30
        radius: 999

        // Filled when selected, outlined when not
        color: root.selected ? "#7a6a5a" : "transparent"
        border.width: root.selected ? 0 : 2
        border.color: "#ffffffcc"

        // Outer shadow ring makes the outline visible against any thumbnail
        Rectangle {
            visible: !root.selected
            anchors.centerIn: parent
            width: parent.width + 2; height: parent.height + 2
            radius: 999
            color: "transparent"
            border.width: 1
            border.color: "#44000000"
            z: -1
        }

        Text {
            anchors.centerIn: parent
            visible: root.selected
            text: root.selectionIndex > 0 ? root.selectionIndex.toString() : "✓"
            font.pixelSize: 14
            font.weight: Font.Bold
            color: "#fff8f4"
        }

        MouseArea {
            anchors.fill: parent
            anchors.margins: -6   // extra touch target padding
            onClicked: {
                mouse.accepted = true
                root.checkboxTapped()
            }
        }
    }
}
