// Compare page — top/bottom synchronized playback of two videos on the mirror.
// Controls operate on the mirror's MediaPlayers via playbackService signals.
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
            title: "Compare Looks"
            subtitle: "Synchronized playback  ·  Mirror is showing top/bottom comparison."
            onBackClicked: {
                if (playbackService) playbackService.close_active()
                if (appController) appController.showGallery()
            }
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

        // ── Controls ─────────────────────────────────────────────────
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
                    if (playbackService) playbackService.close_active()
                    if (appController) appController.showGallery()
                }
            }
        }
    }
}
