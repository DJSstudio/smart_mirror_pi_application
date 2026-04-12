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

        // ── Local preview (silent) ───────────────────────────────────
        MediaSurface {
            Layout.fillWidth: true
            Layout.fillHeight: true
            primarySource: playbackService ? playbackService.primarySource : ""
            primaryLabel: playbackService ? playbackService.primaryLabel : ""
            muted: false
            looping: true
        }

        // ── Mirror status ────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            height: 38
            radius: 10
            color: "#e8e0da"

            Text {
                anchors { fill: parent; leftMargin: 14 }
                verticalAlignment: Text.AlignVCenter
                text: "Mirror is playing this video on the secondary display."
                font.pixelSize: 13
                color: "#7a746e"
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
