// Compare page — top/bottom synchronized playback of two videos on the mirror.
// Control screen has hidden players for scrub/play/pause; mirror renders both.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtMultimedia
import "../components"

Item {
    id: root

    property bool paused: false
    property bool fillCrop: settingsController ? settingsController.compareFillCrop : true

    // Sync timer: every 150 ms align the two players
    Timer {
        id: syncTimer
        interval: 150
        repeat: true
        running: !paused
        onTriggered: _syncPlayers()
    }

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

    ColumnLayout {
        anchors { fill: parent; margins: 24 }
        spacing: 12

        // ── Header ──────────────────────────────────────────────────
        PageHeader {
            Layout.fillWidth: true
            title: "Compare Looks"
            subtitle: "Synchronized playback  ·  Mirror is showing top/bottom comparison."
            onBackClicked: {
                syncTimer.stop()
                leftPlayer.stop()
                rightPlayer.stop()
                if (playbackService) playbackService.close_active()
                if (appController) appController.showGallery()
            }
        }

        // ── Hidden players for scrub/play/pause control ────────────────
        // Video renders on the mirror only — these players provide position
        // tracking for the scrub bar without decoding to a visible surface.
        MediaPlayer {
            id: leftPlayer
            source: playbackService ? playbackService.primarySource : ""
            loops: MediaPlayer.Infinite
            audioOutput: AudioOutput { muted: true }
            Component.onCompleted: play()
        }

        MediaPlayer {
            id: rightPlayer
            source: playbackService ? playbackService.secondarySource : ""
            loops: MediaPlayer.Infinite
            audioOutput: AudioOutput { muted: true }
            Component.onCompleted: play()
        }

        // ── Mirror info panel (comparison plays on mirror only) ──────
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
                    text: "Comparison is playing on the mirror"
                    font.pixelSize: 20
                    font.weight: Font.Medium
                    color: "#C4956A"
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: {
                        var l = playbackService ? playbackService.primaryLabel : ""
                        var r = playbackService ? playbackService.secondaryLabel : ""
                        if (l.length > 0 && r.length > 0) return l + "  /  " + r
                        return "Top vs Bottom"
                    }
                    font.pixelSize: 14
                    color: "#6B635C"
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
