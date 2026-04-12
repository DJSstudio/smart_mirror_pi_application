// Thin status / error banner that appears at the bottom of the control window.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property string statusText: ""
    property string errorText: ""

    readonly property bool hasError: errorText.length > 0

    height: 42
    color: hasError ? "#8c3a3a" : "#e8e0da"
    border.width: 0

    RowLayout {
        anchors { fill: parent; leftMargin: 16; rightMargin: 16 }
        spacing: 10

        Text {
            Layout.fillWidth: true
            text: root.hasError ? ("⚠  " + root.errorText) : root.statusText
            font.pixelSize: 13
            color: root.hasError ? "#fff0ee" : "#7a746e"
            elide: Text.ElideRight
        }

        // Dismiss button when there is an error
        Rectangle {
            visible: root.hasError
            width: 24; height: 24
            radius: 999
            color: "#ffffff30"

            Text {
                anchors.centerIn: parent
                text: "✕"
                font.pixelSize: 12
                color: "#fff0ee"
            }

            MouseArea {
                anchors.fill: parent
                onClicked: appController.clearError()
            }
        }
    }
}
