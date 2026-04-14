// Login page — shown while waiting for a phone to scan the mirror QR code.
import QtQuick
import QtQuick.Layouts
import "../components"

Item {
    id: root

    // Warm off-white background
    Rectangle { anchors.fill: parent; color: "#F7F5F2" }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(parent.width * 0.7, 480)
        spacing: 0

        // ── Brand ────────────────────────────────────────────────────
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: "Smart Mirror"
            font.family: "Noto Serif, Georgia, serif"
            font.pixelSize: 36
            font.weight: Font.Medium
            color: "#1C1917"
        }

        Item { Layout.preferredHeight: 8 }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            text: "Scan the QR code on the mirror with your phone\nto start or resume your session"
            font.pixelSize: 15
            color: "#6B6560"
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }

        Item { Layout.preferredHeight: 40 }

        // ── QR code card ─────────────────────────────────────────────
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 240; height: 240
            radius: 20
            color: loginController.qrImageUrl.length > 0 ? "#FFFFFF" : "#F0EBE5"
            border.width: 1
            border.color: "#E8E2DC"

            Image {
                visible: loginController.qrImageUrl.length > 0
                anchors { fill: parent; margins: 14 }
                source: loginController.qrImageUrl
                fillMode: Image.PreserveAspectFit
                smooth: false
                cache: false
            }

            // Loading pulse
            Rectangle {
                visible: loginController.qrImageUrl.length === 0
                         && loginController.errorMessage.length === 0
                anchors.centerIn: parent
                width: 16; height: 16; radius: 8
                color: "#C4956A"

                SequentialAnimation on opacity {
                    running: parent.visible
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.2; duration: 600 }
                    NumberAnimation { to: 1.0; duration: 600 }
                }
            }
        }

        Item { Layout.preferredHeight: 32 }

        // ── Waiting indicator ─────────────────────────────────────────
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 10
            visible: loginController.isPending && loginController.errorMessage.length === 0

            Rectangle {
                width: 8; height: 8; radius: 4
                color: "#C4956A"

                SequentialAnimation on opacity {
                    running: loginController.isPending
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.2; duration: 700 }
                    NumberAnimation { to: 1.0; duration: 700 }
                }
            }

            Text {
                text: "Waiting for device scan…"
                font.pixelSize: 14
                color: "#6B6560"
            }
        }

        // ── Error ─────────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            visible: loginController.errorMessage.length > 0
            height: 44; radius: 12
            color: "#8B2E2E"

            Text {
                anchors { fill: parent; leftMargin: 16; rightMargin: 16 }
                verticalAlignment: Text.AlignVCenter
                text: "⚠  " + loginController.errorMessage
                font.pixelSize: 13
                color: "#FFFFFF"
                elide: Text.ElideRight
            }
        }
    }
}
