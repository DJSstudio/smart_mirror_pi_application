// Live Compare page — saved video (left) vs live camera feed (right).
// Mirror shows full-screen split.
import QtQuick
import QtQuick.Layouts
import QtMultimedia
import "../components"

Item {
    id: root

    property bool fillCrop: settingsController.compareFillCrop

    ColumnLayout {
        anchors { fill: parent; margins: 24 }
        spacing: 12

        // ── Header ──────────────────────────────────────────────────
        PageHeader {
            Layout.fillWidth: true
            title: "Live Compare"
            subtitle: "Saved look (left)  vs  live camera (right)  ·  Mirror is active."
            onBackClicked: {
                videoPlayer.stop()
                livePlayer.stop()
                playbackService.close_active()
                appController.showGallery()
            }
        }

        // ── Dual pane ────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            // Saved video (looping)
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 16; color: "#0d0b09"
                border.width: 1; border.color: "#1c1814"
                clip: true

                MediaPlayer {
                    id: videoPlayer
                    source: playbackService.primarySource
                    loops: MediaPlayer.Infinite
                    videoOutput: videoOut
                    audioOutput: AudioOutput { muted: true }
                    Component.onCompleted: play()
                }

                VideoOutput {
                    id: videoOut
                    anchors.fill: parent
                    fillMode: root.fillCrop
                        ? VideoOutput.PreserveAspectCrop
                        : VideoOutput.PreserveAspectFit
                }

                // Label
                Rectangle {
                    anchors { left: parent.left; top: parent.top; margins: 10 }
                    radius: 999; color: "#aa0a0907"
                    width: lblSaved.implicitWidth + 14; height: 24
                    Text { id: lblSaved; anchors.centerIn: parent
                           text: playbackService.primaryLabel
                           font.pixelSize: 12; font.weight: Font.DemiBold; color: "#f0ebe5" }
                }
            }

            // Live camera feed
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 16; color: "#0d0b09"
                border.width: 1; border.color: "#1c1814"
                clip: true

                MediaPlayer {
                    id: livePlayer
                    source: playbackService.secondarySource
                    loops: MediaPlayer.Infinite
                    videoOutput: liveOut
                    audioOutput: AudioOutput { muted: true }
                    Component.onCompleted: play()
                }

                VideoOutput {
                    id: liveOut
                    anchors.fill: parent
                    fillMode: root.fillCrop
                        ? VideoOutput.PreserveAspectCrop
                        : VideoOutput.PreserveAspectFit
                }

                // Pulsing live badge
                Rectangle {
                    anchors { right: parent.right; top: parent.top; margins: 10 }
                    radius: 999; color: "#aa8c2020"
                    width: liveLbl.implicitWidth + 14; height: 24

                    Text { id: liveLbl; anchors.centerIn: parent
                           text: "● LIVE"
                           font.pixelSize: 12; font.weight: Font.DemiBold; color: "#ffb8b8"

                        SequentialAnimation on opacity {
                            running: true; loops: Animation.Infinite
                            NumberAnimation { to: 0.4; duration: 700 }
                            NumberAnimation { to: 1.0; duration: 700 }
                        }
                    }
                }

                // Guide overlay toggle
                Text {
                    anchors { left: parent.left; top: parent.top; margins: 10 }
                    text: "LIVE"
                    font.pixelSize: 12; font.weight: Font.DemiBold; color: "#f0ebe5"
                    visible: false
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
                    settingsController.setCompareFillCrop(root.fillCrop)
                }
            }

            AppButton {
                Layout.fillWidth: true
                text: "✕  Close"
                variant: "danger"
                onClicked: {
                    videoPlayer.stop()
                    livePlayer.stop()
                    playbackService.close_active()
                    appController.showGallery()
                }
            }
        }
    }
}
