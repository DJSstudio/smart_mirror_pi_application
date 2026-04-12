// Export / Share page
// Shows a QR code on the control screen (and mirror) that phones scan
// to download a video or browse the session gallery.
import QtQuick
import QtQuick.Layouts
import "../components"

Item {
    id: root

    ColumnLayout {
        anchors { fill: parent; margins: 24 }
        spacing: 16

        // ── Header ──────────────────────────────────────────────────
        PageHeader {
            Layout.fillWidth: true
            title: exportController.mode === "export" ? "Export Video" : "View on Phone"
            subtitle: exportController.mode === "export"
                      ? "Scan the QR code to download the video to your phone."
                      : "Scan to open your session gallery on your phone."
            onBackClicked: exportController.close()
        }

        // ── QR card ─────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 20
            color: "#0d0b09"
            border.width: 1
            border.color: "#1c1814"

            // Error state
            ColumnLayout {
                anchors.centerIn: parent
                visible: exportController.errorMessage.length > 0
                spacing: 12

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "⚠"
                    font.pixelSize: 40
                    color: "#e05050"
                }
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: 280
                    text: exportController.errorMessage
                    font.pixelSize: 13
                    color: "#d0b8b8"
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Install qrcode: pip install \"qrcode[pil]\""
                    font.pixelSize: 11
                    color: "#7a6a6a"
                }
            }

            // QR code + info
            ColumnLayout {
                anchors.centerIn: parent
                visible: exportController.errorMessage.length === 0
                         && exportController.qrImageUrl.length > 0
                spacing: 20

                // QR image in white mat (mirrors the phone's scanner UI)
                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 220; height: 220
                    radius: 16
                    color: "white"

                    Image {
                        anchors { fill: parent; margins: 12 }
                        source: exportController.qrImageUrl
                        fillMode: Image.PreserveAspectFit
                        smooth: false   // keep QR pixels crisp
                        cache: false    // always reload on change
                    }
                }

                // Expiry countdown (export mode only)
                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    visible: exportController.mode === "export"
                    radius: 999
                    color: exportController.remainingSeconds < 120
                           ? "#7a2c2c" : "#2c3a2c"
                    width: expiryRow.implicitWidth + 20; height: 30

                    RowLayout {
                        id: expiryRow
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: "⏱"
                            font.pixelSize: 13
                            color: "#d0d8d0"
                        }
                        Text {
                            text: "Expires in " + exportController.remainingText
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            color: exportController.remainingSeconds < 120
                                   ? "#ffb8b8" : "#b8d8b8"
                        }
                    }
                }

                // URL hint
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: 260
                    text: exportController.serverUrl
                    font.pixelSize: 11
                    color: "#6a6460"
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideMiddle
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: exportController.mode === "export"
                          ? "Mirror is also showing this QR code."
                          : "Mirror is showing the QR code. Scan from the mirror or here."
                    font.pixelSize: 12
                    color: "#7a746e"
                }
            }

            // Loading state
            Text {
                anchors.centerIn: parent
                visible: exportController.errorMessage.length === 0
                         && exportController.qrImageUrl.length === 0
                text: "Generating QR…"
                font.pixelSize: 14
                color: "#6a6460"
            }
        }

        // ── Actions ──────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            AppButton {
                Layout.fillWidth: true
                text: "Done"
                onClicked: exportController.close()
            }
        }
    }
}
