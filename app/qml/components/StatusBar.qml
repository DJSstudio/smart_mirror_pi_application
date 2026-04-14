// Status / error bar at the bottom of the control window.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    property string statusText: ""
    property string errorText: ""

    readonly property bool hasError: errorText.length > 0

    height: 40
    color: hasError ? "#8B2E2E" : "#1C1917"

    Behavior on color { ColorAnimation { duration: 200 } }

    RowLayout {
        anchors { fill: parent; leftMargin: 16; rightMargin: 12 }
        spacing: 10

        Text {
            Layout.fillWidth: true
            text: root.hasError ? ("⚠  " + root.errorText) : root.statusText
            font.pixelSize: 13
            color: root.hasError ? "#FFFFFF" : "#6B635C"
            elide: Text.ElideRight
        }

        // Dismiss on error
        Rectangle {
            visible: root.hasError
            width: 26; height: 26; radius: 999
            color: "#FFFFFF22"

            Text {
                anchors.centerIn: parent
                text: "✕"
                font.pixelSize: 12
                color: "#FFFFFF"
            }

            MouseArea {
                anchors.fill: parent
                onClicked: if (appController) appController.clearError()
            }
        }
    }
}
