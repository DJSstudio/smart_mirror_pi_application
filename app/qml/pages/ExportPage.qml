// Export / Share page — QR code for phone download or session gallery.
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
            title: exportController.mode === "export" ? "Share This Look" : "View on Phone"
            subtitle: exportController.mode === "export"
                      ? "Scan the QR code to download this recording to your phone."
                      : "Scan to open your session gallery on your phone."
            onBackClicked: exportController.close()
        }

        // ── QR card ─────────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 20
            color: "#FFFFFF"
            border.width: 1
            border.color: "#E8E2DC"

            // Error state
            ColumnLayout {
                anchors.centerIn: parent
                visible: exportController.errorMessage.length > 0
                spacing: 12

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 64; height: 64; radius: 999
                    color: "#FFF0F0"

                    Text {
                        anchors.centerIn: parent
                        text: "⚠"
                        font.pixelSize: 28
                        color: "#8B2E2E"
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: 300
                    text: exportController.errorMessage
                    font.pixelSize: 14
                    color: "#1C1917"
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }
            }

            // QR + info
            ColumnLayout {
                anchors.centerIn: parent
                visible: exportController.errorMessage.length === 0
                         && exportController.qrImageUrl.length > 0
                spacing: 24

                // QR in white mat with subtle shadow border
                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 230; height: 230
                    radius: 20
                    color: "#FFFFFF"
                    border.width: 1
                    border.color: "#E8E2DC"

                    Image {
                        anchors { fill: parent; margins: 14 }
                        source: exportController.qrImageUrl
                        fillMode: Image.PreserveAspectFit
                        smooth: false
                        cache: false
                    }
                }

                // Expiry countdown (export mode only)
                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    visible: exportController.mode === "export"
                    radius: 999
                    color: exportController.remainingSeconds < 120 ? "#FFF0F0" : "#F0F7F0"
                    border.width: 1
                    border.color: exportController.remainingSeconds < 120 ? "#E8C0C0" : "#B8D8B8"
                    width: _expRow.implicitWidth + 24; height: 36

                    RowLayout {
                        id: _expRow
                        anchors.centerIn: parent
                        spacing: 8

                        Text {
                            text: "⏱"
                            font.pixelSize: 14
                            color: exportController.remainingSeconds < 120 ? "#8B2E2E" : "#2E6B3A"
                        }

                        Text {
                            text: "Expires in " + exportController.remainingText
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: exportController.remainingSeconds < 120 ? "#8B2E2E" : "#2E6B3A"
                        }
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: exportController.mode === "export"
                          ? "The mirror is also showing this QR code."
                          : "The QR code is also shown on the mirror."
                    font.pixelSize: 13
                    color: "#A09890"
                }
            }

            // Loading
            Text {
                anchors.centerIn: parent
                visible: exportController.errorMessage.length === 0
                         && exportController.qrImageUrl.length === 0
                text: "Generating…"
                font.pixelSize: 15
                color: "#A09890"
            }
        }

        // ── Done ─────────────────────────────────────────────────────
        AppButton {
            Layout.fillWidth: true
            implicitHeight: 56
            text: "Done"
            onClicked: exportController.close()
        }
    }
}
