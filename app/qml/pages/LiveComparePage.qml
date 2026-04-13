// Live Compare page — saved video (top) vs live camera feed (bottom).
// Mirror shows full-screen split.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtMultimedia
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
                videoPlayer.stop()
                livePlayer.stop()
                if (playbackService) playbackService.close_active()
                if (appController) appController.showGallery()
            }
        }

        // ── Dual pane ────────────────────────────────────────────────
        ColumnLayout {
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
                    source: playbackService ? playbackService.primarySource : ""
                    loops: MediaPlayer.Infinite
                    videoOutput: videoOut
                    audioOutput: AudioOutput { muted: true }
                    Component.onCompleted: play()
                }

                Item {
                    anchors.fill: parent
                    layer.enabled: mirrorDisplay && mirrorDisplay.orientationDegrees !== 0
                    transform: Rotation {
                        angle: mirrorDisplay ? mirrorDisplay.orientationDegrees : 0
                        origin.x: parent.width / 2
                        origin.y: parent.height / 2
                    }
                    VideoOutput {
                        id: videoOut
                        anchors.fill: parent
                        fillMode: root.fillCrop
                            ? VideoOutput.PreserveAspectCrop
                            : VideoOutput.PreserveAspectFit
                    }
                }

                // Label
                Rectangle {
                    anchors { left: parent.left; top: parent.top; margins: 10 }
                    radius: 999; color: "#aa0a0907"
                    width: lblSaved.implicitWidth + 14; height: 24
                    Text { id: lblSaved; anchors.centerIn: parent
                           text: playbackService ? playbackService.primaryLabel : ""
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
                    source: playbackService ? playbackService.secondarySource : ""
                    loops: MediaPlayer.Infinite
                    videoOutput: liveOut
                    audioOutput: AudioOutput { muted: true }
                    Component.onCompleted: play()
                }

                Item {
                    anchors.fill: parent
                    layer.enabled: mirrorDisplay && mirrorDisplay.orientationDegrees !== 0
                    transform: Rotation {
                        angle: mirrorDisplay ? mirrorDisplay.orientationDegrees : 0
                        origin.x: parent.width / 2
                        origin.y: parent.height / 2
                    }
                    VideoOutput {
                        id: liveOut
                        anchors.fill: parent
                        fillMode: root.fillCrop
                            ? VideoOutput.PreserveAspectCrop
                            : VideoOutput.PreserveAspectFit
                    }
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
                    if (settingsController) settingsController.setCompareFillCrop(root.fillCrop)
                }
            }

            AppButton {
                Layout.fillWidth: true
                text: "✕  Close"
                variant: "danger"
                onClicked: {
                    videoPlayer.stop()
                    livePlayer.stop()
                    if (playbackService) playbackService.close_active()
                    if (appController) appController.showGallery()
                }
            }
        }
    }
}
