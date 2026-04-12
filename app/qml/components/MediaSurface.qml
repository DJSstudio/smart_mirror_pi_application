import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia

Item {
    id: root

    property string primarySource: ""
    property string secondarySource: ""
    property string primaryLabel: ""
    property string secondaryLabel: ""
    property bool splitView: false
    property bool fillCrop: false
    property bool showGuides: false
    property bool muted: true
    property bool loop: true
    property int orientationDegrees: 0
    property color backgroundColor: "#050505"

    Rectangle {
        anchors.fill: parent
        radius: 30
        color: root.backgroundColor
        border.width: 1
        border.color: "#221d19"
    }

    Loader {
        anchors.fill: parent
        sourceComponent: root.splitView ? splitSurface : singleSurface
    }

    component VideoPane: Item {
        id: pane

        property string sourceUrl: ""
        property string labelText: ""
        property bool showOverlayGuides: false

        Rectangle {
            anchors.fill: parent
            radius: 26
            color: "#080808"
        }

        MediaPlayer {
            id: player
            source: pane.sourceUrl
            loops: root.loop ? MediaPlayer.Infinite : 1
            videoOutput: videoOutput
            audioOutput: AudioOutput {
                muted: root.muted
                volume: root.muted ? 0.0 : 1.0
            }
            onSourceChanged: {
                if (pane.sourceUrl.length > 0) {
                    play()
                } else {
                    stop()
                }
            }
        }

        Item {
            anchors.fill: parent
            layer.enabled: root.orientationDegrees !== 0
            transform: Rotation {
                angle: root.orientationDegrees
                origin.x: pane.width / 2
                origin.y: pane.height / 2
            }

            VideoOutput {
                id: videoOutput
                anchors.fill: parent
                fillMode: root.fillCrop ? VideoOutput.PreserveAspectCrop : VideoOutput.PreserveAspectFit
            }
        }

        Item {
            anchors.fill: parent
            visible: pane.showOverlayGuides

            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.58
                height: parent.height * 0.82
                radius: 24
                color: "transparent"
                border.width: 2
                border.color: "#e4d1bf"
            }

            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.002
                height: parent.height * 0.82
                color: "#bfa891"
                opacity: 0.55
            }

            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.58
                height: parent.height * 0.002
                color: "#bfa891"
                opacity: 0.55
            }
        }

        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.margins: 14
            radius: 999
            color: "#99171210"
            visible: pane.labelText.length > 0
            width: label.implicitWidth + 18
            height: label.implicitHeight + 10

            Text {
                id: label
                anchors.centerIn: parent
                text: pane.labelText
                color: "#f6efe8"
                font.family: "Noto Serif"
                font.pixelSize: 16
                font.weight: Font.DemiBold
            }
        }

        Text {
            anchors.centerIn: parent
            visible: pane.sourceUrl.length === 0
            text: "Awaiting source"
            color: "#b9ae9f"
            font.family: "Noto Serif"
            font.pixelSize: 22
        }
    }

    Component {
        id: singleSurface

        VideoPane {
            anchors.fill: parent
            anchors.margins: 14
            sourceUrl: root.primarySource
            labelText: root.primaryLabel
            showOverlayGuides: root.showGuides
        }
    }

    Component {
        id: splitSurface

        RowLayout {
            anchors.fill: parent
            anchors.margins: 14
            spacing: 14

            VideoPane {
                Layout.fillWidth: true
                Layout.fillHeight: true
                sourceUrl: root.primarySource
                labelText: root.primaryLabel
            }

            VideoPane {
                Layout.fillWidth: true
                Layout.fillHeight: true
                sourceUrl: root.secondarySource
                labelText: root.secondaryLabel
                showOverlayGuides: root.showGuides
            }
        }
    }
}
