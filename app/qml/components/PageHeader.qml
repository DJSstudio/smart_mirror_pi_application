// Reusable page header with back button, title, and subtitle.
import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property bool showBack: true

    signal backClicked()

    implicitHeight: col.implicitHeight + 32

    ColumnLayout {
        id: col
        anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 20 }
        spacing: 4

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            // Back arrow
            Rectangle {
                visible: root.showBack
                width: 36; height: 36
                radius: 999
                color: backMa.containsMouse ? "#e2dbd5" : "#ece4dd"
                border.width: 1
                border.color: "#c4b8ac"

                Text {
                    anchors.centerIn: parent
                    text: "←"
                    font.pixelSize: 18
                    color: "#3c3530"
                }

                MouseArea {
                    id: backMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.backClicked()
                }
            }

            Text {
                Layout.fillWidth: true
                text: root.title
                font.family: "Noto Serif, Georgia, serif"
                font.pixelSize: 22
                font.weight: Font.Medium
                color: "#3c3530"
                elide: Text.ElideRight
            }
        }

        Text {
            visible: root.subtitle.length > 0
            Layout.leftMargin: root.showBack ? 48 : 0
            text: root.subtitle
            font.family: "Noto Sans, system-ui, sans-serif"
            font.pixelSize: 13
            color: "#8c8681"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
    }
}
