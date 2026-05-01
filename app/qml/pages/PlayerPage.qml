// Video player page — plays the selected video on the mirror, previews it here.
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
            title: playbackService
                   ? (playbackService.primaryLabel.length > 0 ? playbackService.primaryLabel : "Look Review")
                   : "Look Review"
            subtitle: "Mirror is active. Playback is controlled here."
            onBackClicked: {
                if (playbackService) playbackService.close_active()
                if (appController) appController.showGallery()
            }
        }

        // ── Mirror info panel (video plays on mirror only) ────────────
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
                    text: "Video is playing on the mirror"
                    font.pixelSize: 20
                    font.weight: Font.Medium
                    color: "#C4956A"
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: playbackService && playbackService.primaryLabel.length > 0
                          ? playbackService.primaryLabel
                          : ""
                    font.pixelSize: 14
                    color: "#6B635C"
                }
            }
        }

        // ── Actions ──────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            AppButton {
                Layout.fillWidth: true
                text: "Back to Gallery"
                variant: "secondary"
                onClicked: {
                    if (playbackService) playbackService.close_active()
                    if (appController) appController.showGallery()
                }
            }

            AppButton {
                Layout.fillWidth: true
                text: "Export to Phone"
                onClicked: {
                    if (exportController && playbackService)
                        exportController.exportVideo(playbackService.currentVideoId)
                }
            }

            AppButton {
                Layout.fillWidth: true
                text: "Close Player"
                onClicked: {
                    if (playbackService) playbackService.close_active()
                    if (appController) appController.showDashboard()
                }
            }
        }
    }
}
