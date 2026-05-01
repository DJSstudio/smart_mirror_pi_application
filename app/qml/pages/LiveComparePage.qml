// Live Compare page — saved video (top) vs live camera feed (bottom).
// Mirror shows full-screen split.
import QtQuick
import QtQuick.Layouts
import "../components"

Item {
    id: root

    property bool fillCrop: settingsController ? settingsController.compareFillCrop : true

    ColumnLayout {
        anchors { fill: parent; margins: 24 }
        spacing: 12

        // ── Header ──────────────────────────────────────────────────
        PageHeader {
            Layout.fillWidth: true
            title: "Live Compare"
            subtitle: "Saved look (left)  vs  live camera (right)  ·  Mirror is active."
            onBackClicked: {
                if (playbackService) playbackService.close_active()
                if (appController) appController.showGallery()
            }
        }

        // ── Mirror info panel (comparison plays on mirror only) ────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 20
            color: "#0D0B09"
            border.width: 1
            border.color: "#1C1917"

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 18

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 80; height: 80; radius: 999
                    color: "#1C1917"

                    Text {
                        anchors.centerIn: parent
                        text: "🪞"
                        font.pixelSize: 36
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Live comparison is on the mirror"
                    font.pixelSize: 20
                    font.weight: Font.Medium
                    color: "#C4956A"
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: playbackService && playbackService.primaryLabel.length > 0
                          ? (playbackService.primaryLabel + "  vs  Live camera")
                          : "Saved look vs Live camera"
                    font.pixelSize: 14
                    color: "#6B635C"
                }
            }
        }

        // ── Controls ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            AppButton {
                Layout.fillWidth: true
                text: root.fillCrop ? "Fit Mode" : "Crop Mode"
                variant: "secondary"
                onClicked: {
                    root.fillCrop = !root.fillCrop
                    if (settingsController) settingsController.setCompareFillCrop(root.fillCrop)
                }
            }

            AppButton {
                Layout.fillWidth: true
                text: "✕  Close"
                variant: "danger"
                onClicked: {
                    if (playbackService) playbackService.close_active()
                    if (appController) appController.showGallery()
                }
            }
        }
    }
}
