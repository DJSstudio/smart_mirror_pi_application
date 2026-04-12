// Login page — shown on the control window while waiting for a phone to scan
// the QR code displayed on the mirror.
import QtQuick
import QtQuick.Layouts
import "../components"

Item {
    id: root

    ColumnLayout {
        anchors { fill: parent; margins: 40 }
        spacing: 0

        Item { Layout.fillHeight: true }

        // ── Title ────────────────────────────────────────────────────
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: "Smart Mirror"
            font.family: "Noto Serif, Georgia, serif"
            font.pixelSize: 32
            font.weight: Font.Medium
            color: "#3c3530"
        }

        Item { Layout.preferredHeight: 8 }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 360
            text: "Scan the QR code on the mirror with your phone to start or resume your session"
            font.pixelSize: 14
            color: "#8c8681"
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }

        Item { Layout.preferredHeight: 32 }

        // ── QR preview (same code as mirror, for convenience) ────────
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 180; height: 180
            radius: 16
            color: loginController.qrImageUrl.length > 0 ? "white" : "#ede5de"
            border.width: 1
            border.color: "#d6cdc5"

            Image {
                visible: loginController.qrImageUrl.length > 0
                anchors { fill: parent; margins: 12 }
                source: loginController.qrImageUrl
                fillMode: Image.PreserveAspectFit
                smooth: false
                cache: false
            }

            // Pulsing dot while QR is generating (no QtQuick.Controls needed)
            Rectangle {
                visible: loginController.qrImageUrl.length === 0
                         && loginController.errorMessage.length === 0
                anchors.centerIn: parent
                width: 20; height: 20; radius: 10
                color: "#b0a8a0"

                SequentialAnimation on opacity {
                    running: parent.visible
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.2; duration: 600 }
                    NumberAnimation { to: 1.0; duration: 600 }
                }
            }
        }

        Item { Layout.preferredHeight: 16 }

        // ── Server URL hint ──────────────────────────────────────────
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: loginController.serverUrl
            font.pixelSize: 11
            color: "#a09590"
            horizontalAlignment: Text.AlignHCenter
        }

        Item { Layout.preferredHeight: 24 }

        // ── Waiting indicator ────────────────────────────────────────
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 8
            visible: loginController.isPending && loginController.errorMessage.length === 0

            Rectangle {
                width: 8; height: 8; radius: 4
                color: "#7a6a5a"

                SequentialAnimation on opacity {
                    running: loginController.isPending
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.2; duration: 700 }
                    NumberAnimation { to: 1.0; duration: 700 }
                }
            }

            Text {
                text: "Waiting for device scan…"
                font.pixelSize: 13
                color: "#9d9590"
            }
        }

        // ── Error state ──────────────────────────────────────────────
        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 320
            visible: loginController.errorMessage.length > 0
            text: "⚠  " + loginController.errorMessage
            font.pixelSize: 12
            color: "#c05050"
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
        }

        Item { Layout.fillHeight: true }

        // ── Skip button ──────────────────────────────────────────────
        AppButton {
            Layout.alignment: Qt.AlignHCenter
            text: "Continue without scan"
            variant: "secondary"
            onClicked: loginController.skipLogin()
        }

        Item { Layout.preferredHeight: 16 }
    }
}
