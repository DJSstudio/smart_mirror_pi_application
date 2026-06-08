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

        // ── Framing guide — shown during live preview (recording) ────
        // Two horizontal lines at 25 % and 75 %, two vertical lines at
        // 25 % and 75 %, forming a centred guide box over the live feed.
        Item {
            id: framingGuide
            anchors.fill: parent
            visible: mirrorDisplay && mirrorDisplay.mode === "live_preview"

            // Top line — 25 % from top
            Rectangle {
                anchors { left: parent.left; right: parent.right }
                y: parent.height * 0.25
                height: 1
                color: "#55ffffff"
            }
            // Bottom line — 25 % from bottom
            Rectangle {
                anchors { left: parent.left; right: parent.right }
                y: parent.height * 0.75
                height: 1
                color: "#55ffffff"
            }
            // Left line — 25 % from left
            Rectangle {
                anchors { top: parent.top; bottom: parent.bottom }
                x: parent.width * 0.25
                width: 1
                color: "#55ffffff"
            }
            // Right line — 25 % from right
            Rectangle {
                anchors { top: parent.top; bottom: parent.bottom }
                x: parent.width * 0.75
                width: 1
                color: "#55ffffff"
            }
        }

        // ── REC + elapsed time overlay (top-right, orientation-aware) ──
        // A wrapper Item rotated by mirrorOrientationDegrees with the badge
        // anchored to top-right.  After rotation the badge appears at the
        // user's perceived top-right regardless of physical mirror orientation.
        Item {
            id: recOverlayWrapper
            visible: recordingController
                     && recordingController.isRecording
                     && recordingController.countdown === 0
            anchors.centerIn: parent

            // Swap dimensions for 90°/270° rotations so the badge lands
            // at the corner the user sees as top-right.
            property int orient: mirrorDisplay ? mirrorDisplay.orientationDegrees : 0
            width: (orient === 90 || orient === 270) ? parent.height : parent.width
            height: (orient === 90 || orient === 270) ? parent.width  : parent.height

            transform: Rotation {
                angle: recOverlayWrapper.orient
                origin.x: recOverlayWrapper.width / 2
                origin.y: recOverlayWrapper.height / 2
            }

            Rectangle {
                anchors { top: parent.top; right: parent.right; margins: 24 }
                radius: 999
                width: _mirrorRecRow.implicitWidth + 24
                height: 48
                color: "#CC8B2E2E"
                border.width: 1
                border.color: "#FF6B6B"

                RowLayout {
                    id: _mirrorRecRow
                    anchors.centerIn: parent
                    spacing: 12

                    Rectangle {
                        width: 14; height: 14; radius: 999
                        color: "#FF6B6B"

                        SequentialAnimation on opacity {
                            running: recOverlayWrapper.visible
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.25; duration: 600 }
                            NumberAnimation { to: 1.0;  duration: 600 }
                        }
                    }

                    Text {
                        text: "REC"
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1.5
                        color: "#FFFFFF"
                    }

                    Rectangle {
                        width: 1; height: 22
                        color: "#88FFFFFF"
                    }

                    Text {
                        text: recordingController ? recordingController.elapsedText : "00:00"
                        font.family: "Noto Sans Mono, Consolas, monospace"
                        font.pixelSize: 18
                        font.weight: Font.Medium
                        color: "#FFFFFF"
                    }
                }
            }
        }

        // ── Pre-recording countdown overlay ──────────────────────────
        // Shown while the camera pipeline warms up so subjects see a
        // clean countdown instead of pixelated warm-up frames.
        Rectangle {
            id: mirrorCountdownOverlay
            anchors.fill: parent
            visible: recordingController ? recordingController.countdown > 0 : false
            color: "#d9000000"
            transform: Rotation {
                angle: mirrorDisplay ? mirrorDisplay.orientationDegrees : 0
                origin.x: mirrorCountdownOverlay.width  / 2
                origin.y: mirrorCountdownOverlay.height / 2
            }

            Column {
                anchors.centerIn: parent
                spacing: 20

                Text {
                    id: mirrorCountNum
                    anchors.horizontalCenter: parent.horizontalCenter
                    text: recordingController && recordingController.countdown > 0
                          ? recordingController.countdown.toString() : ""
                    font.pixelSize: Math.min(mirrorWindow.width, mirrorWindow.height) * 0.35
                    font.weight: Font.Bold
                    color: "#fff8f4"
                    opacity: 0.92

                    SequentialAnimation on scale {
                        running: recordingController ? recordingController.countdown > 0 : false
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
        // ── Idle auto-logout warning overlay (mirror side) ──────────
        // Mirrors the ControlWindow overlay so the person in front of the
        // mirror can see the countdown too.  Instructs them to interact with
        // the controller screen (not the mirror itself).
        Rectangle {
            id: mirrorIdleOverlay
            anchors.fill: parent
            z: 100
            visible: idleService && idleService.warningVisible
            color: "#E6000000"

            ColumnLayout {
                anchors.centerIn: parent
                spacing: 32

                // Countdown ring
                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 160; height: 160; radius: 80
                    color: "transparent"
                    border.width: 5
                    border.color: "#C4956A"

                    Text {
                        anchors.centerIn: parent
                        text: idleService ? idleService.secondsLeft : ""
                        font.pixelSize: 72
                        font.weight: Font.Bold
                        color: "#FFFFFF"
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Still there?"
                    font.pixelSize: 40
                    font.weight: Font.Bold
                    color: "#FFFFFF"
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Tap anywhere on the controller screen to stay logged in"
                    font.pixelSize: 22
                    color: "#B0A89E"
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }

    // ── Live preview (recording mode) ────────────────────────────────
    // Architecture: ffmpeg subprocess captures the real USB camera and
    // writes frames to /dev/video10 (v4l2loopback) AND records H.264 to file.
    // QCamera (Python: QtCameraSession) opens /dev/video10 as a regular
    // camera and pushes frames to the VideoOutput's videoSink for direct,
    // low-latency rendering — same path proven by scripts/test_qcamera.py.
    Component {
        id: livePreviewComp
        Item {
            id: _liveFlipWrapper
            transform: Scale {
                xScale: settingsController.cameraMirrorFlip ? -1 : 1
                origin.x: _liveFlipWrapper.width / 2
            }
            VideoOutput {
                id: qtLiveOut
                anchors.fill: parent
                fillMode: VideoOutput.PreserveAspectFit
                Component.onCompleted: {
                    if (qtCamera) qtCamera.attachSink(qtLiveOut.videoSink)
                }
                Component.onDestruction: {
                    if (qtCamera) qtCamera.detachSink()
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
                // Report playback state back to controller via playbackService
                onPositionChanged: if (playbackService) playbackService.setMirrorPosition(position)
                onDurationChanged: if (playbackService) playbackService.setMirrorDuration(duration)
                onPlaybackStateChanged: {
                    if (playbackService)
                        playbackService.setMirrorPlaying(playbackState === MediaPlayer.PlayingState)
                }
            }
            VideoOutput {
                id: videoOut
                anchors.fill: parent
                fillMode: VideoOutput.PreserveAspectFit
            }
            // Listen for control commands from controller-screen UI
            Connections {
                target: playbackService
                function onPlayRequested() { videoPlayer.play() }
                function onPauseRequested() { videoPlayer.pause() }
                function onSeekRequested(pos) { videoPlayer.position = pos }
            }
        }
    }

    // ── Top/bottom compare ───────────────────────────────────────────
    // Both panes share play/pause via playbackService.  The PRIMARY (top)
    // pane is authoritative for position/duration reporting; the SECONDARY
    // pane mirrors primary's seek for sync.
    Component {
        id: compareComp
        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            MirrorPane {
                Layout.fillWidth: true
                Layout.fillHeight: true
                source: mirrorDisplay.primarySource
                labelText: mirrorDisplay.primaryLabel
                fillCrop: mirrorDisplay.compareFillCrop
                isPrimary: true
            }

            Rectangle { height: 2; Layout.fillWidth: true; color: "#111111" }

            MirrorPane {
                Layout.fillWidth: true
                Layout.fillHeight: true
                source: mirrorDisplay.secondarySource
                labelText: mirrorDisplay.secondaryLabel
                fillCrop: mirrorDisplay.compareFillCrop
                isPrimary: false
            }
        }
    }

    // ── Live compare (saved top + live feed bottom) ───────────────────
    // Top: saved video file via MediaPlayer.
    // Bottom: live USB camera via QCamera direct (same low-latency path as
    // the recording-mode live preview).  No MediaPlayer for the live half
    // — the QtCameraSession pushes frames into the VideoOutput's videoSink.
    Component {
        id: liveCompareComp
        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            MirrorPane {
                Layout.fillWidth: true
                Layout.fillHeight: true
                source: mirrorDisplay.primarySource
                labelText: mirrorDisplay.primaryLabel
                fillCrop: mirrorDisplay.compareFillCrop
                looping: true
                isPrimary: true   // saved video is controllable via playbackService
            }

            Rectangle { height: 2; Layout.fillWidth: true; color: "#111111" }

            // Live camera pane — Qt-direct, same approach as livePreviewComp
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                VideoOutput {
                    id: liveCmpOut
                    anchors.fill: parent
                    fillMode: mirrorDisplay.compareFillCrop
                        ? VideoOutput.PreserveAspectCrop
                        : VideoOutput.PreserveAspectFit
                    Component.onCompleted: {
                        if (qtCamera) qtCamera.attachSink(liveCmpOut.videoSink)
                    }
                    Component.onDestruction: {
                        if (qtCamera) qtCamera.detachSink()
                    }
                }

                // "● LIVE" badge so users know the bottom pane is real-time
                Rectangle {
                    visible: true
                    anchors { right: parent.right; top: parent.top; margins: 18 }
                    radius: 999
                    color: "#bb7a1414"
                    width: liveBadgeText.implicitWidth + 16
                    height: 28

                    Text {
                        id: liveBadgeText
                        anchors.centerIn: parent
                        text: "● LIVE"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        color: "#ffb8b8"

                        SequentialAnimation on opacity {
                            running: true
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.3; duration: 800 }
                            NumberAnimation { to: 1.0; duration: 800 }
                        }
                    }
                }
            }
        }
    }

    // ── QR code display ──────────────────────────────────────────────
    Component {
        id: qrCodeComp
        Item {
            transform: Rotation {
                angle: mirrorDisplay ? mirrorDisplay.orientationDegrees : 0
                origin.x: width / 2
                origin.y: height / 2
            }

            Rectangle {
                anchors.fill: parent
                color: "#000000"

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 36

                    // White mat around the QR — large enough to fill most of the mirror
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: Math.min(mirrorWindow.width, mirrorWindow.height) * 0.75
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
    // When `isPrimary` is true, this pane reports its position/duration/
    // playback state to playbackService and listens for play/pause/seek
    // commands from it.  Secondary panes silently mirror primary's seeks
    // (so split-compare stays in sync).
    component MirrorPane: Item {
        id: pane

        property string source: ""
        property string labelText: ""
        property bool fillCrop: false
        property bool muted: false
        property bool looping: true
        property bool showLiveBadge: false
        property int rotation: 0
        property bool isPrimary: false

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
                if (pane.isPrimary && playbackService) {
                    playbackService.setMirrorPlaying(playbackState === MediaPlayer.PlayingState)
                }
            }
            onPositionChanged: {
                if (pane.isPrimary && playbackService)
                    playbackService.setMirrorPosition(position)
            }
            onDurationChanged: {
                if (pane.isPrimary && playbackService)
                    playbackService.setMirrorDuration(duration)
            }
            onErrorOccurred: function(error, errorString) {
                console.error("MirrorPane error (" + pane.source + "):", errorString)
                if (pane.looping && pane.source.length > 0)
                    mirrorRetry.restart()
            }
        }

        // Listen for control commands from controller-screen UI.  All panes
        // (primary AND secondary) react, so split-compare stays in sync.
        Connections {
            target: playbackService
            function onPlayRequested() { panePlayer.play() }
            function onPauseRequested() { panePlayer.pause() }
            function onSeekRequested(pos) { panePlayer.position = pos }
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
