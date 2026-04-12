import QtQuick
import QtQuick.Window

import "components"

Window {
    id: mirrorWindow
    objectName: "mirrorWindow"
    visible: false
    width: 1280
    height: 720
    color: "black"
    title: "Mirror Output"
    flags: Qt.Window | Qt.FramelessWindowHint

    Rectangle {
        anchors.fill: parent
        color: "black"
    }

    MediaSurface {
        anchors.fill: parent
        visible: mirrorDisplay.mode !== "idle" && mirrorDisplay.mode !== "test_pattern"
        primarySource: mirrorDisplay.primarySource
        secondarySource: mirrorDisplay.secondarySource
        primaryLabel: mirrorDisplay.primaryLabel
        secondaryLabel: mirrorDisplay.secondaryLabel
        splitView: mirrorDisplay.mode === "compare" || mirrorDisplay.mode === "live_compare"
        fillCrop: splitView ? mirrorDisplay.compareFillCrop : false
        orientationDegrees: mirrorDisplay.orientationDegrees
        showGuides: mirrorDisplay.mode === "recording_preview"
    }

    Item {
        anchors.fill: parent
        visible: mirrorDisplay.mode === "test_pattern"

        Rectangle {
            anchors.fill: parent
            color: "#050505"
        }

        Repeater {
            model: 10
            Rectangle {
                width: parent.width
                height: 1
                y: index * (mirrorWindow.height / 10)
                color: index === 5 ? "#dd9d5f" : "#42352d"
            }
        }

        Repeater {
            model: 10
            Rectangle {
                width: 1
                height: parent.height
                x: index * (mirrorWindow.width / 10)
                color: index === 5 ? "#dd9d5f" : "#42352d"
            }
        }

        Text {
            anchors.centerIn: parent
            text: "Mirror Test Pattern"
            color: "#f0e3d6"
            font.family: "Noto Serif"
            font.pixelSize: 42
        }
    }
}
