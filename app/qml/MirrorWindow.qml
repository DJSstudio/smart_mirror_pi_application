// Mirror Window — lives on Display 2.
// Always exists, never destroyed. Defaults to pure black.
// Renders content only when MirrorDisplayService commands it.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtMultimedia

ApplicationWindow {
    id: mirrorWindow
    objectName: "mirrorWindow"

    // Hidden initially; screen_manager will call showFullScreen()
    visible: false
    width: 1920
    height: 1080
    title: "Mirror"
    // Do NOT add WindowStaysOnBottomHint here — on X11 and many Wayland
    // compositors that hint sets a sub-normal window level which silently
    // prevents showFullScreen() from working.  The mirror is on its own
    // dedicated display so there is nothing it needs to stay below.
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "#000000"

    // ── Root black canvas ────────────────────────────────────────────
    Rectangle {
        id: canvas
        anchors.fill: parent
        color: "#000000"

        // ── Mode dispatcher ──────────────────────────────────────────
        Loader {
            id: modeLoader
            anchors.fill: parent
            sourceComponent: mirrorDisplay ? _pickComponent(mirrorDisplay.mode) : null

            function _pickComponent(mode) {
                switch (mode) {
                    case "live_preview":  return livePreviewComp
                    case "video":         return videoComp
                    case "compare":       return compareComp
                    case "live_compare":  return liveCompareComp
                    case "test_pattern":  return testPatternComp
                    case "qr_code":       return qrCodeComp
                    default:              return null   // idle → pure black
                }
            }

        }

        // ── Pre-recording countdown overlay ──────────────────────────
        // Shown while the camera pipeline warms up so subjects see a
        // clean countdown instead of pixelated warm-up frames.
        Rectangle {
            id: mirrorCountdownOverlay
            anchors.fill: parent
            visible: recordingController.countdown > 0
            color: "#d9000000"

            Column {
                anchors.centerIn: parent
                spacing: 20

                Text {
                    id: mirrorCountNum
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: recordingController.countdown > 0
                          ? recordingController.countdown.toString() : ""
                    font.pixelSize: Math.min(mirrorWindow.width, mirrorWindow.height) * 0.35
                    font.weight: Font.Bold
                    color: "#fff8f4"
                    opacity: 0.92

                    SequentialAnimation on scale {
                        running: recordingController.countdown > 0
                        loops: Animation.Infinite
                        NumberAnimation { to: 1.12; duration: 300; easing.type: Easing.OutQuad }
                        NumberAnimation { to: 1.0;  duration: 700; easing.type: Easing.InQuad }
                    }
                }

                Text {
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: "Get ready…"
                    font.pixelSize: Math.min(mirrorWindow.width, mirrorWindow.height) * 0.04
                    color: "#d0c8c0"
                }
            }
        }
    }

    // ── Live preview (recording mode) ────────────────────────────────
    Component {
        id: livePreviewComp
        Item {
            MediaPlayer {
                id: livePlayer
                source: mirrorDisplay.primarySource
                loops: MediaPlayer.Infinite
                videoOutput: liveOut
                audioOutput: AudioOutput { muted: true }
                Component.onCompleted: play()
                onSourceChanged: { stop(); if (source.toString().length) play() }
            }
            VideoOutput {
                id: liveOut
                anchors.fill: parent
                // Crop to fill the whole mirror — no black bars.
                // A real mirror shows edge-to-edge; letterboxing would look wrong.
                fillMode: VideoOutput.PreserveAspectCrop

                transform: Rotation {
                    angle: mirrorDisplay.orientationDegrees
                    origin.x: liveOut.width / 2
                    origin.y: liveOut.height / 2
                }
            }
        }
    }

    // ── Single video playback ────────────────────────────────────────
    Component {
        id: videoComp
        Item {
            MediaPlayer {
                id: videoPlayer
                source: mirrorDisplay.primarySource
                loops: MediaPlayer.Infinite
                videoOutput: videoOut
                audioOutput: AudioOutput { muted: false; volume: 1.0 }
                Component.onCompleted: play()
                onSourceChanged: { stop(); if (source.toString().length) play() }
            }
            VideoOutput {
                id: videoOut
                anchors.fill: parent
                fillMode: VideoOutput.PreserveAspectCrop

                transform: Rotation {
                    angle: mirrorDisplay.orientationDegrees
                    origin.x: videoOut.width / 2
                    origin.y: videoOut.height / 2
                }
            }
        }
    }

    // ── Side-by-side compare ─────────────────────────────────────────
    Component {
        id: compareComp
        RowLayout {
            anchors.fill: parent
            spacing: 0

            MirrorPane {
                Layout.fillWidth: true
                Layout.fillHeight: true
                source: mirrorDisplay.primarySource
                labelText: mirrorDisplay.primaryLabel
                fillCrop: mirrorDisplay.compareFillCrop
                rotation: mirrorDisplay.orientationDegrees
            }

            Rectangle { width: 2; Layout.fillHeight: true; color: "#111111" }

            MirrorPane {
                Layout.fillWidth: true
                Layout.fillHeight: true
                source: mirrorDisplay.secondarySource
                labelText: mirrorDisplay.secondaryLabel
                fillCrop: mirrorDisplay.compareFillCrop
                rotation: mirrorDisplay.orientationDegrees
            }
        }
    }

    // ── Live compare (saved + live feed) ─────────────────────────────
    Component {
        id: liveCompareComp
        RowLayout {
            anchors.fill: parent
            spacing: 0

            MirrorPane {
                Layout.fillWidth: true
                Layout.fillHeight: true
                source: mirrorDisplay.primarySource
                labelText: mirrorDisplay.primaryLabel
                fillCrop: mirrorDisplay.compareFillCrop
                looping: true
            }

            Rectangle { width: 2; Layout.fillHeight: true; color: "#111111" }

            MirrorPane {
                Layout.fillWidth: true
                Layout.fillHeight: true
                source: mirrorDisplay.secondarySource
                labelText: mirrorDisplay.secondaryLabel
                fillCrop: mirrorDisplay.compareFillCrop
                looping: true
                muted: true
                showLiveBadge: true
            }
        }
    }

    // ── QR code display ──────────────────────────────────────────────
    Component {
        id: qrCodeComp
        Item {
            Rectangle {
                anchors.fill: parent
                color: "#000000"

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 36

                    // White mat around the QR so it scans from any distance
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: Math.min(mirrorWindow.width, mirrorWindow.height) * 0.45
                        height: width
                        radius: 20
                        color: "white"

                        Image {
                            anchors { fill: parent; margins: 16 }
                            source: mirrorDisplay.primarySource
                            fillMode: Image.PreserveAspectFit
                            smooth: false   // keep QR pixels crisp
                            cache: false
                        }
                    }

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: mirrorDisplay.primaryLabel
                        font.pixelSize: Math.min(mirrorWindow.width, mirrorWindow.height) * 0.03
                        color: "#c8c0b8"
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }
    }

    // ── Test pattern ─────────────────────────────────────────────────
    Component {
        id: testPatternComp
        Item {
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.5
                height: parent.height * 0.5
                radius: 24
                color: "#1c1c24"
                border.width: 2
                border.color: "#4a6a8a"

                Column {
                    anchors.centerIn: parent
                    spacing: 12

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Mirror Test Pattern"
                        font.pixelSize: 32
                        color: "#c8d8e8"
                        font.weight: Font.Light
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: mirrorWindow.width + " × " + mirrorWindow.height
                        font.pixelSize: 18
                        color: "#8898a8"
                    }

                    // Colour bars
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 4
                        Repeater {
                            model: ["#e05050", "#e0a050", "#e0e050", "#50e050", "#5050e0", "#9050e0", "#e050e0"]
                            Rectangle { width: 40; height: 20; radius: 4; color: modelData }
                        }
                    }
                }
            }
        }
    }

    // ── MirrorPane: reusable single-video pane ───────────────────────
    component MirrorPane: Item {
        id: pane

        property string source: ""
        property string labelText: ""
        property bool fillCrop: false
        property bool muted: false
        property bool looping: true
        property bool showLiveBadge: false
        property int rotation: 0

        MediaPlayer {
            id: panePlayer
            source: pane.source
            loops: pane.looping ? MediaPlayer.Infinite : 1
            videoOutput: paneOut
            audioOutput: AudioOutput { muted: pane.muted; volume: pane.muted ? 0 : 1 }
            Component.onCompleted: { if (pane.source.length) play() }
            onSourceChanged: { stop(); if (source.toString().length) play() }
            onPlaybackStateChanged: {
                if (playbackState === MediaPlayer.StoppedState
                        && pane.looping && pane.source.length > 0) {
                    Qt.callLater(function() { play() })
                }
            }
            onErrorOccurred: function(error, errorString) {
                console.error("MirrorPane error (" + pane.source + "):", errorString)
                if (pane.looping && pane.source.length > 0)
                    mirrorRetry.restart()
            }
        }

        Timer {
            id: mirrorRetry
            interval: 1500; repeat: false
            onTriggered: { if (pane.source.length > 0) { panePlayer.stop(); panePlayer.play() } }
        }

        VideoOutput {
            id: paneOut
            anchors.fill: parent
            fillMode: pane.fillCrop
                ? VideoOutput.PreserveAspectCrop
                : VideoOutput.PreserveAspectFit

            transform: Rotation {
                angle: pane.rotation
                origin.x: paneOut.width / 2
                origin.y: paneOut.height / 2
            }
        }

        // Label
        Rectangle {
            visible: pane.labelText.length > 0
            anchors { left: parent.left; bottom: parent.bottom; margins: 18 }
            radius: 999; color: "#bb0a0906"
            width: paneLbl.implicitWidth + 16; height: 28

            Text {
                id: paneLbl
                anchors.centerIn: parent
                text: pane.labelText
                font.pixelSize: 14
                font.weight: Font.DemiBold
                color: "#f0ebe5"
            }
        }

        // Live badge
        Rectangle {
            visible: pane.showLiveBadge
            anchors { right: parent.right; top: parent.top; margins: 18 }
            radius: 999; color: "#bb7a1414"
            width: liveTxt.implicitWidth + 16; height: 28

            Text {
                id: liveTxt
                anchors.centerIn: parent
                text: "● LIVE"
                font.pixelSize: 13
                font.weight: Font.DemiBold
                color: "#ffb8b8"

                SequentialAnimation on opacity {
                    running: pane.showLiveBadge
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.3; duration: 800 }
                    NumberAnimation { to: 1.0; duration: 800 }
                }
            }
        }
    }
}
