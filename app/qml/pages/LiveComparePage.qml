// Live Compare page — saved video (top) vs live camera feed (bottom).
// Mirror shows full-screen split.  Controls drive the saved video pane via
// playbackService; Record button captures the live camera feed to gallery.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
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
            subtitle: "Saved look (top)  vs  live camera (bottom)  ·  Mirror is active."
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
                    color: playbackService && playbackService.liveCompareRecording
                           ? "#8B2E2E" : "#1C1917"

                    Text {
                        anchors.centerIn: parent
                        text: playbackService && playbackService.liveCompareRecording
                              ? "●" : "🪞"
                        font.pixelSize: 36
                        color: playbackService && playbackService.liveCompareRecording
                               ? "#FF6B6B" : "#C4956A"

                        SequentialAnimation on opacity {
                            running: playbackService && playbackService.liveCompareRecording
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.4; duration: 600 }
                            NumberAnimation { to: 1.0; duration: 600 }
                        }
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: playbackService && playbackService.liveCompareRecording
                          ? "Recording live camera…"
                          : "Live comparison is on the mirror"
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

        // ── Scrub bar (saved video on top of mirror) ─────────────────
        Slider {
            Layout.fillWidth: true
            from: 0
            to: playbackService && playbackService.mirrorDuration > 0
                ? playbackService.mirrorDuration : 1
            value: playbackService ? playbackService.mirrorPosition : 0
            stepSize: 500
            onMoved: { if (playbackService) playbackService.requestSeek(value) }

            background: Rectangle {
                x: parent.leftPadding
                y: parent.topPadding + parent.availableHeight / 2 - height / 2
                width: parent.availableWidth
                height: 4; radius: 2
                color: "#e2dbd5"

                Rectangle {
                    width: parent.width * parent.parent.visualPosition
                    height: parent.height; radius: 2
                    color: "#c9bfb7"
                }
            }
            handle: Rectangle {
                x: parent.leftPadding + parent.visualPosition * (parent.availableWidth - width)
                y: parent.topPadding + parent.availableHeight / 2 - height / 2
                width: 16; height: 16; radius: 999
                color: "#8c8077"
            }
        }

        // ── Saved-video transport ────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            AppButton {
                text: "−10s"
                variant: "secondary"
                implicitWidth: 72
                onClicked: { if (playbackService) playbackService.requestSeekRelative(-10000) }
            }

            AppButton {
                Layout.fillWidth: true
                text: (playbackService && playbackService.isPlaying) ? "⏸  Pause" : "▶  Play"
                onClicked: { if (playbackService) playbackService.requestTogglePlayPause() }
            }

            AppButton {
                text: "+10s"
                variant: "secondary"
                implicitWidth: 72
                onClicked: { if (playbackService) playbackService.requestSeekRelative(10000) }
            }
        }

        // ── Recording + utility row ──────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            AppButton {
                Layout.fillWidth: true
                text: (playbackService && playbackService.liveCompareRecording)
                      ? "■  Stop Recording"
                      : "●  Record Live"
                variant: (playbackService && playbackService.liveCompareRecording) ? "danger" : "primary"
                onClicked: {
                    if (!playbackService) return
                    if (playbackService.liveCompareRecording)
                        playbackService.stopLiveCompareRecording()
                    else
                        playbackService.startLiveCompareRecording()
                }
            }

            AppButton {
                text: root.fillCrop ? "Fit" : "Crop"
                variant: "ghost"
                implicitWidth: 90
                onClicked: {
                    root.fillCrop = !root.fillCrop
                    if (settingsController) settingsController.setCompareFillCrop(root.fillCrop)
                }
            }

            AppButton {
                text: "✕  Close"
                variant: "secondary"
                onClicked: {
                    // Stop any active recording before closing
                    if (playbackService && playbackService.liveCompareRecording)
                        playbackService.stopLiveCompareRecording()
                    if (playbackService) playbackService.close_active()
                    if (appController) appController.showGallery()
                }
            }
        }
    }
}
