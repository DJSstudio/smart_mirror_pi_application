// Compare page — top/bottom synchronized playback of two videos.
// Both the control screen (silent) and the mirror (full screen split) are active.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtMultimedia
import "../components"

Item {
    id: root

    // Sync timer: every 150 ms align the two players
    Timer {
        id: syncTimer
        interval: 150
        repeat: true
        running: !paused
        onTriggered: _syncPlayers()
    }

    property bool paused: false
    property bool fillCrop: settingsController ? settingsController.compareFillCrop : true

    // ── Helpers ────────────────────────────────────────────────────
    function _syncPlayers() {
        if (!leftPlayer.playing && !paused) {
            leftPlayer.play()
            rightPlayer.play()
            return
        }
        var diff = Math.abs(leftPlayer.position - rightPlayer.position)
        if (diff > 200) {
            rightPlayer.position = leftPlayer.position
        }
    }

    function _togglePlay() {
        paused = !paused
        if (paused) {
            leftPlayer.pause()
            rightPlayer.pause()
        } else {
            leftPlayer.play()
            rightPlayer.play()
        }
    }

    function _seek(deltaMs) {
        var pos = Math.max(0, leftPlayer.position + deltaMs)
        leftPlayer.position = pos
        rightPlayer.position = pos
    }

    // ──────────────────────────────────────────────────────────────

    ColumnLayout {
        anchors { fill: parent; margins: 24 }
        spacing: 12

        // ── Header ──────────────────────────────────────────────────
        PageHeader {
            Layout.fillWidth: true
            title: "Compare Looks"
            subtitle: "Synchronized playback  ·  Mirror is showing left/right comparison."
            onBackClicked: {
                syncTimer.stop()
                leftPlayer.stop()
                rightPlayer.stop()
                if (playbackService) playbackService.close_active()
                if (appController) appController.showGallery()
            }
        }

        // ── Split preview ────────────────────────────────────────────
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 12

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 16
                color: "#0d0b09"
                border.color: "#1c1814"
                border.width: 1
                clip: true

                MediaPlayer {
                    id: leftPlayer
                    source: playbackService ? playbackService.primarySource : ""
                    loops: MediaPlayer.Infinite
                    videoOutput: leftOutput
                    audioOutput: AudioOutput { muted: true }
                    Component.onCompleted: play()
                }

                VideoOutput {
                    id: leftOutput
                    anchors.fill: parent
                    fillMode: root.fillCrop
                        ? VideoOutput.PreserveAspectCrop
                        : VideoOutput.PreserveAspectFit
                }

                Rectangle {
                    anchors { left: parent.left; top: parent.top; margins: 10 }
                    radius: 999; color: "#aa0a0907"
                    width: lblLeft.implicitWidth + 14; height: 24
                    Text { id: lblLeft; anchors.centerIn: parent; text: playbackService ? playbackService.primaryLabel : ""
                           font.pixelSize: 12; font.weight: Font.DemiBold; color: "#f0ebe5" }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 16
                color: "#0d0b09"
                border.color: "#1c1814"
                border.width: 1
                clip: true

                MediaPlayer {
                    id: rightPlayer
                    source: playbackService ? playbackService.secondarySource : ""
                    loops: MediaPlayer.Infinite
                    videoOutput: rightOutput
                    audioOutput: AudioOutput { muted: true }
                    Component.onCompleted: play()
                }

                VideoOutput {
                    id: rightOutput
                    anchors.fill: parent
                    fillMode: root.fillCrop
                        ? VideoOutput.PreserveAspectCrop
                        : VideoOutput.PreserveAspectFit
                }

                Rectangle {
                    anchors { left: parent.left; top: parent.top; margins: 10 }
                    radius: 999; color: "#aa0a0907"
                    width: lblRight.implicitWidth + 14; height: 24
                    Text { id: lblRight; anchors.centerIn: parent; text: playbackService ? playbackService.secondaryLabel : ""
                           font.pixelSize: 12; font.weight: Font.DemiBold; color: "#f0ebe5" }
                }
            }
        }

        // ── Scrub bar ────────────────────────────────────────────────
        Slider {
            Layout.fillWidth: true
            from: 0
            to: leftPlayer.duration > 0 ? leftPlayer.duration : 1
            value: leftPlayer.position
            stepSize: 500
            onMoved: {
                leftPlayer.position = value
                rightPlayer.position = value
            }

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

        // ── Controls ─────────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            AppButton {
                text: "−10s"
                variant: "secondary"
                implicitWidth: 72
                onClicked: root._seek(-10000)
            }

            AppButton {
                Layout.fillWidth: true
                text: root.paused ? "▶  Play" : "⏸  Pause"
                onClicked: root._togglePlay()
            }

            AppButton {
                text: "+10s"
                variant: "secondary"
                implicitWidth: 72
                onClicked: root._seek(10000)
            }

            AppButton {
                text: root.fillCrop ? "Fit" : "Crop"
                variant: "ghost"
                implicitWidth: 72
                onClicked: {
                    root.fillCrop = !root.fillCrop
                    if (settingsController) settingsController.setCompareFillCrop(root.fillCrop)
                }
            }

            AppButton {
                text: "✕  Close"
                variant: "secondary"
                onClicked: {
                    syncTimer.stop()
                    leftPlayer.stop()
                    rightPlayer.stop()
                    if (playbackService) playbackService.close_active()
                    if (appController) appController.showGallery()
                }
            }
        }
    }
}
