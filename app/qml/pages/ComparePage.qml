// Compare page — plays a single pre-combined vstacked file on the mirror.
// Combine happens in PlaybackService.open_compare() so the Pi only does ONE
// H.264 decode instead of two (its hardware decoder is single-instance).
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtMultimedia
import "../components"

Item {
    id: root

    property bool paused: false
    property bool fillCrop: settingsController ? settingsController.compareFillCrop : true

    function _togglePlay() {
        paused = !paused
        if (paused) player.pause(); else player.play()
    }

    function _seek(deltaMs) {
        var pos = Math.max(0, player.position + deltaMs)
        player.position = pos
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
                player.stop()
                if (playbackService) playbackService.close_active()
                if (appController) appController.showGallery()
            }
        }

        // ── Hidden player for scrub/play/pause control ────────────────
        // The actual video renders only on the mirror.  This player tracks
        // position so the scrub bar and ±10s controls can drive playback.
        MediaPlayer {
            id: player
            source: playbackService ? playbackService.primarySource : ""
            loops: MediaPlayer.Infinite
            audioOutput: AudioOutput { muted: true }
            onSourceChanged: { if (source.toString().length > 0) play() }
        }

        // ── Mirror info panel ────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 20
            color: "#0D0B09"
            border.width: 1
            border.color: "#1C1917"

            // Preparing state: ffmpeg is combining the two clips
            ColumnLayout {
                anchors.centerIn: parent
                visible: playbackService && playbackService.comparePending
                spacing: 18

                BusyIndicator {
                    Layout.alignment: Qt.AlignHCenter
                    running: parent.visible
                    width: 56; height: 56
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Preparing comparison…"
                    font.pixelSize: 18
                    color: "#C4956A"
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Combining the two clips into one stream for smooth playback."
                    font.pixelSize: 13
                    color: "#6B635C"
                }
            }

            // Error state
            ColumnLayout {
                anchors.centerIn: parent
                visible: playbackService && playbackService.compareError.length > 0
                spacing: 12

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "⚠"
                    font.pixelSize: 48
                    color: "#FF6B6B"
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: playbackService ? playbackService.compareError : ""
                    font.pixelSize: 14
                    color: "#FF9999"
                    wrapMode: Text.Wrap
                    horizontalAlignment: Text.AlignHCenter
                    Layout.maximumWidth: 480
                }
            }

            // Ready state: show "playing on mirror" hint
            ColumnLayout {
                anchors.centerIn: parent
                visible: playbackService
                         && !playbackService.comparePending
                         && playbackService.compareError.length === 0
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
            enabled: playbackService && !playbackService.comparePending
            from: 0
            to: player.duration > 0 ? player.duration : 1
            value: player.position
            stepSize: 500
            onMoved: player.position = value

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
                enabled: playbackService && !playbackService.comparePending
                onClicked: root._seek(-10000)
            }

            AppButton {
                Layout.fillWidth: true
                text: root.paused ? "▶  Play" : "⏸  Pause"
                enabled: playbackService && !playbackService.comparePending
                onClicked: root._togglePlay()
            }

            AppButton {
                text: "+10s"
                variant: "secondary"
                implicitWidth: 72
                enabled: playbackService && !playbackService.comparePending
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
                    player.stop()
                    if (playbackService) playbackService.close_active()
                    if (appController) appController.showGallery()
                }
            }
        }
    }
}
