// Video player surface used in the control window pages (not the mirror).
// Handles single-pane and split-pane layouts with Qt Multimedia.
import QtQuick
import QtQuick.Layouts
import QtMultimedia

Item {
    id: root

    // ---------------------------------------------------------------
    // Public API
    // ---------------------------------------------------------------
    property string primarySource: ""
    property string secondarySource: ""
    property string primaryLabel: ""
    property string secondaryLabel: ""
    property bool splitView: false
    property bool fillCrop: false
    property bool showGuides: false
    property bool muted: true
    property bool looping: true
    property int orientationDegrees: 0
    property color backgroundColor: "#0a0907"

    // Expose playback position — written by the active VideoPane via Connections
    property real primaryPosition: 0
    property real primaryDuration: 0

    signal primaryFinished()
    signal secondaryFinished()

    // ---------------------------------------------------------------
    // Background
    // ---------------------------------------------------------------
    Rectangle {
        anchors.fill: parent
        radius: 20
        color: root.backgroundColor
        border.width: 1
        border.color: "#1c1814"
    }

    Loader {
        anchors { fill: parent; margins: 12 }
        sourceComponent: root.splitView ? splitComp : singleComp
    }

    // ---------------------------------------------------------------
    // Single pane
    // ---------------------------------------------------------------
    Component {
        id: singleComp
        VideoPane {
            id: primaryPane
            anchors.fill: parent
            sourceUrl: root.primarySource
            labelText: root.primaryLabel
            fillCrop: root.fillCrop
            muted: root.muted
            looping: root.looping
            orientationDegrees: root.orientationDegrees
            showGuides: root.showGuides
            onFinished: root.primaryFinished()
        }
    }

    // ---------------------------------------------------------------
    // Split pane
    // ---------------------------------------------------------------
    Component {
        id: splitComp
        RowLayout {
            anchors.fill: parent
            spacing: 10

            VideoPane {
                id: primaryPane
                Layout.fillWidth: true
                Layout.fillHeight: true
                sourceUrl: root.primarySource
                labelText: root.primaryLabel
                fillCrop: root.fillCrop
                muted: root.muted
                looping: root.looping
                orientationDegrees: root.orientationDegrees
                onFinished: root.primaryFinished()
            }

            VideoPane {
                id: secondaryPane
                Layout.fillWidth: true
                Layout.fillHeight: true
                sourceUrl: root.secondarySource
                labelText: root.secondaryLabel
                fillCrop: root.fillCrop
                muted: root.muted
                looping: root.looping
                orientationDegrees: root.orientationDegrees
                showGuides: root.showGuides
                onFinished: root.secondaryFinished()
            }
        }
    }

    // ---------------------------------------------------------------
    // VideoPane component
    // ---------------------------------------------------------------
    component VideoPane: Item {
        id: pane

        property string sourceUrl: ""
        property string labelText: ""
        property bool fillCrop: false
        property bool muted: true
        property bool looping: true
        property int orientationDegrees: 0
        property bool showGuides: false
        property real position: player.position
        property real duration: player.duration

        signal finished()

        function play()       { player.play() }
        function pause()      { player.pause() }
        function seek(ms)     { player.position = ms }

        Rectangle { anchors.fill: parent; radius: 14; color: "#0d0b09" }

        MediaPlayer {
            id: player
            source: pane.sourceUrl
            loops: pane.looping ? MediaPlayer.Infinite : 1
            videoOutput: videoOut
            audioOutput: AudioOutput { muted: pane.muted; volume: pane.muted ? 0 : 1 }

            onSourceChanged: {
                if (pane.sourceUrl.length > 0) play()
                else stop()
            }
            onPlaybackStateChanged: {
                if (playbackState === MediaPlayer.StoppedState) {
                    if (pane.looping && pane.sourceUrl.length > 0) {
                        // GStreamer pipeline can stall on loop — restart cleanly
                        Qt.callLater(function() { play() })
                    } else if (!pane.looping) {
                        pane.finished()
                    }
                }
            }
            onErrorOccurred: function(error, errorString) {
                console.error("MediaPlayer error (" + pane.sourceUrl + "):", errorString)
                if (pane.looping && pane.sourceUrl.length > 0) {
                    // Retry after a short delay so we don't spin on a hard error
                    retryTimer.restart()
                }
            }
        }

        Timer {
            id: retryTimer
            interval: 1500
            repeat: false
            onTriggered: {
                if (pane.sourceUrl.length > 0) {
                    player.stop()
                    player.play()
                }
            }
        }

        Item {
            anchors.fill: parent
            layer.enabled: pane.orientationDegrees !== 0
            transform: Rotation {
                angle: pane.orientationDegrees
                origin.x: pane.width / 2
                origin.y: pane.height / 2
            }

            VideoOutput {
                id: videoOut
                anchors.fill: parent
                fillMode: pane.fillCrop
                    ? VideoOutput.PreserveAspectCrop
                    : VideoOutput.PreserveAspectFit
            }
        }

        // Guide overlay
        Item {
            anchors.fill: parent
            visible: pane.showGuides
            // Vertical centre line
            Rectangle { anchors.centerIn: parent; width: 1; height: parent.height * 0.8; color: "#80c4a882" }
            // Face-framing oval
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.55; height: parent.height * 0.75
                radius: width / 2
                color: "transparent"
                border.width: 1; border.color: "#80c4a882"
            }
        }

        // Label badge
        Rectangle {
            visible: pane.labelText.length > 0
            anchors { left: parent.left; top: parent.top; margins: 10 }
            radius: 999
            color: "#aa0a0907"
            width: lbl.implicitWidth + 14; height: 24

            Text {
                id: lbl
                anchors.centerIn: parent
                text: pane.labelText
                color: "#f0ebe5"
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
        }

        // Empty state
        Text {
            anchors.centerIn: parent
            visible: pane.sourceUrl.length === 0
            text: "No source"
            color: "#6b6560"
            font.pixelSize: 16
        }
    }
}
