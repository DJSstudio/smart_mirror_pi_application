// Reusable page header — back button, title, optional subtitle.
import QtQuick
import QtQuick.Layouts

Item {
    id: root

    property string title: ""
    property string subtitle: ""
    property bool showBack: true

    signal backClicked()

    implicitHeight: _col.implicitHeight + 28

    ColumnLayout {
        id: _col
        anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 16 }
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 14

            // Back button
            Rectangle {
                visible: root.showBack
                width: 42; height: 42; radius: 999
                color: _bkMa.containsMouse ? "#EDE8E3" : "#F0EBE5"
                border.width: 1
                border.color: "#D8D0C8"

                Text {
                    anchors.centerIn: parent
                    text: "←"
                    font.pixelSize: 18
                    color: "#1C1917"
                }

                MouseArea {
                    id: _bkMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.backClicked()
                }
            }

            Text {
                Layout.fillWidth: true
                text: root.title
                font.pixelSize: 24
                font.weight: Font.Bold
                color: "#1C1917"
                elide: Text.ElideRight
            }
        }

        Text {
            visible: root.subtitle.length > 0
            Layout.leftMargin: root.showBack ? 56 : 0
            Layout.fillWidth: true
            text: root.subtitle
            font.pixelSize: 13
            color: "#6B6560"
            wrapMode: Text.WordWrap
        }
    }
}
