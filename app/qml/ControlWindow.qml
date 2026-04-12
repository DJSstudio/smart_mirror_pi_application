import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "components"

ApplicationWindow {
    id: controlWindow
    objectName: "controlWindow"
    visible: false
    width: 1280
    height: 800
    title: "Smart Mirror Pi"
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "#e8ddd2"

    readonly property bool navigationLocked: recordingController.isRecording || recordingController.hasReview || recordingController.countdown > 0
    readonly property string headerTitle: ({
        "dashboard": "Studio Dashboard",
        "recording": "Record Your Look",
        "gallery": "Look Gallery",
        "player": "Playback Review",
        "compare": "Compare Looks",
        "live_compare": "Live Compare",
        "settings": "System Settings"
    })[appController.currentPage] || "Smart Mirror"

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#f4ede6" }
            GradientStop { position: 0.55; color: "#e6d8ca" }
            GradientStop { position: 1.0; color: "#dbc7b6" }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 22
        spacing: 22

        Rectangle {
            Layout.preferredWidth: 280
            Layout.fillHeight: true
            radius: 34
            color: "#f7f1ea"
            border.width: 1
            border.color: "#e1d3c7"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 18

                Text {
                    text: "Atelier Mirror"
                    color: "#46372c"
                    font.family: "Noto Serif"
                    font.pixelSize: 30
                    font.weight: Font.DemiBold
                }

                Text {
                    text: "Debian-first, two-screen Raspberry Pi control surface"
                    color: "#7b6b5f"
                    font.family: "Noto Sans"
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 24
                    color: "#f0e3d6"
                    border.width: 1
                    border.color: "#deccb9"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 8

                        Text {
                            text: "ACTIVE SESSION"
                            color: "#7f6d5d"
                            font.family: "Noto Sans"
                            font.pixelSize: 12
                        }

                        Text {
                            text: sessionController.activeSessionName
                            color: "#44362c"
                            font.family: "Noto Serif"
                            font.pixelSize: 22
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            text: sessionController.clipCount + " saved looks"
                            color: "#7f6d5d"
                            font.family: "Noto Sans"
                            font.pixelSize: 13
                        }
                    }
                }

                AppButton {
                    Layout.fillWidth: true
                    text: "Dashboard"
                    enabled: !navigationLocked || appController.currentPage === "dashboard"
                    onClicked: appController.showDashboard()
                }

                AppButton {
                    Layout.fillWidth: true
                    text: "Record"
                    enabled: !navigationLocked || appController.currentPage === "recording"
                    onClicked: appController.showRecording()
                }

                AppButton {
                    Layout.fillWidth: true
                    text: "Gallery"
                    enabled: !navigationLocked || appController.currentPage === "gallery"
                    onClicked: appController.showGallery()
                }

                AppButton {
                    Layout.fillWidth: true
                    text: "Settings"
                    enabled: !navigationLocked || appController.currentPage === "settings"
                    onClicked: appController.showSettings()
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 22
                    color: "#1d1814"
                    border.width: 1
                    border.color: "#3a312b"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 8

                        Text {
                            text: "MIRROR STATE"
                            color: "#d2c6b9"
                            font.family: "Noto Sans"
                            font.pixelSize: 12
                        }

                        Text {
                            text: mirrorDisplay.statusText
                            color: "#f4ede6"
                            font.family: "Noto Serif"
                            font.pixelSize: 20
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            text: "Mode: " + mirrorDisplay.mode
                            color: "#c1b4a7"
                            font.family: "Noto Sans"
                            font.pixelSize: 12
                        }
                    }
                }

                Item {
                    Layout.fillHeight: true
                }

                AppButton {
                    Layout.fillWidth: true
                    text: "New Session"
                    onClicked: sessionController.newSession("")
                }

                AppButton {
                    Layout.fillWidth: true
                    text: "Mirror Test"
                    onClicked: settingsController.showMirrorTestPattern()
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 38
            color: "#f8f3ee"
            border.width: 1
            border.color: "#e2d5ca"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 26
                spacing: 18

                RowLayout {
                    Layout.fillWidth: true

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Text {
                            text: headerTitle
                            color: "#43352b"
                            font.family: "Noto Serif"
                            font.pixelSize: 34
                            font.weight: Font.DemiBold
                        }

                        Text {
                            text: appController.statusMessage
                            color: "#7b6a5c"
                            font.family: "Noto Sans"
                            font.pixelSize: 14
                            wrapMode: Text.WordWrap
                        }
                    }

                    Rectangle {
                        visible: appController.errorMessage.length > 0
                        radius: 999
                        color: "#f7dbd6"
                        border.width: 1
                        border.color: "#d89d94"
                        width: errorLabel.implicitWidth + 26
                        height: errorLabel.implicitHeight + 14

                        Text {
                            id: errorLabel
                            anchors.centerIn: parent
                            text: appController.errorMessage
                            color: "#7c2d26"
                            font.family: "Noto Sans"
                            font.pixelSize: 13
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: appController.clearError()
                        }
                    }
                }

                Loader {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    sourceComponent: ({
                        "dashboard": dashboardPage,
                        "recording": recordingPage,
                        "gallery": galleryPage,
                        "player": playerPage,
                        "compare": comparePage,
                        "live_compare": liveComparePage,
                        "settings": settingsPage
                    })[appController.currentPage]
                }
            }
        }
    }

    Component {
        id: dashboardPage

        ColumnLayout {
            anchors.fill: parent
            spacing: 18

            RowLayout {
                Layout.fillWidth: true
                spacing: 18

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 30
                    color: "#e8d9c9"
                    border.width: 1
                    border.color: "#d4c1ae"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 24
                        spacing: 10

                        Text {
                            text: "Record new looks with the mirror black until the exact capture flow begins."
                            color: "#4a392c"
                            font.family: "Noto Serif"
                            font.pixelSize: 30
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            text: "Recording activates the mirror, stopping returns the output to a full black idle frame."
                            color: "#735f50"
                            font.family: "Noto Sans"
                            font.pixelSize: 15
                            wrapMode: Text.WordWrap
                        }

                        Item { Layout.fillHeight: true }

                        RowLayout {
                            spacing: 12
                            AppButton {
                                text: "Start Recording"
                                onClicked: appController.showRecording()
                            }
                            AppButton {
                                text: "Open Gallery"
                                onClicked: appController.showGallery()
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 310
                    Layout.fillHeight: true
                    radius: 30
                    color: "#201915"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 22
                        spacing: 12

                        Text {
                            text: "OPERATIONAL STATUS"
                            color: "#d4c7bb"
                            font.family: "Noto Sans"
                            font.pixelSize: 12
                        }

                        Text {
                            text: "Camera: " + settingsController.currentCameraBackendLabel
                            color: "#fbf6f0"
                            font.family: "Noto Serif"
                            font.pixelSize: 22
                        }

                        Text {
                            text: settingsController.dependencySummary
                            color: "#cbbeb1"
                            font.family: "Noto Sans"
                            font.pixelSize: 13
                            wrapMode: Text.WordWrap
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            radius: 22
                            color: "#2d251f"
                            border.width: 1
                            border.color: "#433831"

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 6

                                Text {
                                    text: "DISPLAY ASSIGNMENT"
                                    color: "#cbbeb1"
                                    font.family: "Noto Sans"
                                    font.pixelSize: 12
                                }

                                Text {
                                    text: "Control screen: " + settingsController.controlScreenIndex
                                    color: "#fbf6f0"
                                    font.family: "Noto Serif"
                                    font.pixelSize: 18
                                }

                                Text {
                                    text: "Mirror screen: " + settingsController.mirrorScreenIndex
                                    color: "#fbf6f0"
                                    font.family: "Noto Serif"
                                    font.pixelSize: 18
                                }
                            }
                        }

                        Item { Layout.fillHeight: true }

                        AppButton {
                            Layout.fillWidth: true
                            text: "Blackout Mirror"
                            onClicked: settingsController.blackoutMirror()
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 220
                radius: 30
                color: "#f1e6db"
                border.width: 1
                border.color: "#ddcab8"

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 16

                    Repeater {
                        model: [
                            {
                                "title": "Mirror rule",
                                "body": "Boot, idle, and every workflow gap render as black on Display 2."
                            },
                            {
                                "title": "Capture",
                                "body": "Recordings start from a controlled countdown and land in SQLite-backed gallery records."
                            },
                            {
                                "title": "Playback",
                                "body": "Single playback, compare, and live compare all use the same persistent mirror window."
                            }
                        ]

                        delegate: Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: 24
                            color: "#faf5ef"
                            border.width: 1
                            border.color: "#eaded3"

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 18
                                spacing: 8

                                Text {
                                    text: modelData.title
                                    color: "#44362c"
                                    font.family: "Noto Serif"
                                    font.pixelSize: 22
                                }

                                Text {
                                    text: modelData.body
                                    color: "#78695c"
                                    font.family: "Noto Sans"
                                    font.pixelSize: 14
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: recordingPage

        RowLayout {
            anchors.fill: parent
            spacing: 18

            MediaSurface {
                Layout.fillWidth: true
                Layout.fillHeight: true
                primarySource: recordingController.hasReview ? recordingController.reviewSource : recordingController.previewSource
                primaryLabel: recordingController.hasReview ? "Review" : (recordingController.isRecording ? "Live" : "Preview")
                orientationDegrees: 0
                showGuides: recordingController.isRecording
                fillCrop: false
            }

            Rectangle {
                Layout.preferredWidth: 330
                Layout.fillHeight: true
                radius: 30
                color: "#efe1d3"
                border.width: 1
                border.color: "#d8c1ad"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 20
                    spacing: 12

                    Text {
                        text: "Capture"
                        color: "#43352b"
                        font.family: "Noto Serif"
                        font.pixelSize: 28
                    }

                    Text {
                        text: recordingController.isRecording
                              ? "Mirror is active for recording preview."
                              : recordingController.hasReview
                                ? "Mirror is black. Review locally, then save or discard."
                                : "Mirror will stay black until recording starts."
                        color: "#78695c"
                        font.family: "Noto Sans"
                        font.pixelSize: 14
                        wrapMode: Text.WordWrap
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        radius: 24
                        color: "#f7f0e9"
                        border.width: 1
                        border.color: "#e6d6c8"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 6

                            Text {
                                text: "BACKEND"
                                color: "#7b6b5f"
                                font.family: "Noto Sans"
                                font.pixelSize: 12
                            }

                            Text {
                                text: recordingController.backendLabel
                                color: "#45372d"
                                font.family: "Noto Serif"
                                font.pixelSize: 20
                            }

                            Text {
                                text: recordingController.countdown > 0
                                      ? "Countdown: " + recordingController.countdown
                                      : (recordingController.isRecording ? "Elapsed: " + recordingController.elapsedText : "Ready")
                                color: "#45372d"
                                font.family: "Noto Serif"
                                font.pixelSize: 18
                            }
                        }
                    }

                    RowLayout {
                        spacing: 8
                        Repeater {
                            model: [0, 90, 180, 270]

                            delegate: AppButton {
                                text: modelData + "°"
                                enabled: !recordingController.isRecording
                                onClicked: settingsController.setMirrorOrientation(modelData)
                            }
                        }
                    }

                    Text {
                        text: recordingController.errorMessage
                        color: "#8f2d25"
                        visible: recordingController.errorMessage.length > 0
                        font.family: "Noto Sans"
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                    }

                    Item { Layout.fillHeight: true }

                    AppButton {
                        Layout.fillWidth: true
                        text: "Start Recording"
                        enabled: !recordingController.isBusy && !recordingController.isRecording && !recordingController.hasReview
                        onClicked: recordingController.beginRecording()
                    }

                    AppButton {
                        Layout.fillWidth: true
                        text: "Stop Recording"
                        enabled: recordingController.isRecording && !recordingController.isBusy
                        onClicked: recordingController.stopRecording()
                    }

                    AppButton {
                        Layout.fillWidth: true
                        text: "Save Recording"
                        enabled: recordingController.hasReview && !recordingController.isBusy
                        onClicked: recordingController.saveRecording()
                    }

                    AppButton {
                        Layout.fillWidth: true
                        text: recordingController.hasReview ? "Discard Review" : "Cancel"
                        onClicked: recordingController.discardRecording()
                    }
                }
            }
        }
    }

    Component {
        id: galleryPage

        ColumnLayout {
            anchors.fill: parent
            spacing: 16

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                AppButton {
                    text: "Refresh"
                    onClicked: galleryController.refresh()
                }

                AppButton {
                    text: "Compare"
                    enabled: galleryController.canCompare
                    onClicked: galleryController.startCompare()
                }

                AppButton {
                    text: "Live Compare"
                    enabled: galleryController.canLiveCompare
                    onClicked: galleryController.startLiveCompare()
                }

                AppButton {
                    text: "Clear Selection"
                    enabled: galleryController.selectedIds.length > 0
                    onClicked: galleryController.clearSelection()
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: galleryController.videos.length + " saved looks"
                    color: "#7b6a5c"
                    font.family: "Noto Sans"
                    font.pixelSize: 14
                }
            }

            Flickable {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: width
                contentHeight: galleryFlow.implicitHeight
                clip: true

                Flow {
                    id: galleryFlow
                    width: parent.width
                    spacing: 16

                    Repeater {
                        model: galleryController.videos

                        delegate: Rectangle {
                            required property var modelData

                            width: Math.max(260, (galleryFlow.width - 32) / 3)
                            height: 298
                            radius: 26
                            color: "#f6efe8"
                            border.width: 1
                            border.color: "#e4d6ca"

                            readonly property bool selected: galleryController.selectedIds.indexOf(modelData.id) >= 0

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 10

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 186
                                    radius: 22
                                    color: "#120f0d"
                                    clip: true

                                    Image {
                                        anchors.fill: parent
                                        source: modelData.thumbnailUrl
                                        fillMode: Image.PreserveAspectCrop
                                        visible: source.toString().length > 0
                                    }

                                    Rectangle {
                                        anchors.fill: parent
                                        color: "transparent"
                                        border.width: 2
                                        border.color: selected ? "#d08b52" : "transparent"
                                        radius: 22
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        visible: modelData.thumbnailUrl.length === 0
                                        text: "No thumbnail"
                                        color: "#d5c6b8"
                                        font.family: "Noto Serif"
                                        font.pixelSize: 18
                                    }

                                    Rectangle {
                                        anchors.left: parent.left
                                        anchors.top: parent.top
                                        anchors.margins: 10
                                        radius: 999
                                        color: selected ? "#d08b52" : "#8c7661"
                                        width: badge.implicitWidth + 18
                                        height: badge.implicitHeight + 8

                                        Text {
                                            id: badge
                                            anchors.centerIn: parent
                                            text: selected ? "Selected" : "Preview"
                                            color: "#fff7f0"
                                            font.family: "Noto Sans"
                                            font.pixelSize: 11
                                            font.weight: Font.Bold
                                        }
                                    }
                                }

                                Text {
                                    text: modelData.title
                                    color: "#45372d"
                                    font.family: "Noto Serif"
                                    font.pixelSize: 22
                                    wrapMode: Text.WordWrap
                                }

                                RowLayout {
                                    Layout.fillWidth: true

                                    Text {
                                        text: modelData.durationLabel
                                        color: "#7d6a5b"
                                        font.family: "Noto Sans"
                                        font.pixelSize: 12
                                    }

                                    Item { Layout.fillWidth: true }

                                    Text {
                                        text: modelData.createdLabel
                                        color: "#7d6a5b"
                                        font.family: "Noto Sans"
                                        font.pixelSize: 12
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8

                                    AppButton {
                                        Layout.fillWidth: true
                                        text: "Open"
                                        onClicked: galleryController.openVideo(modelData.id)
                                    }

                                    AppButton {
                                        Layout.fillWidth: true
                                        text: selected ? "Unselect" : "Select"
                                        onClicked: galleryController.toggleSelect(modelData.id)
                                    }

                                    AppButton {
                                        Layout.fillWidth: true
                                        text: "Delete"
                                        onClicked: galleryController.deleteVideo(modelData.id)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: playerPage

        ColumnLayout {
            anchors.fill: parent
            spacing: 16

            MediaSurface {
                Layout.fillWidth: true
                Layout.fillHeight: true
                primarySource: playbackService.primarySource
                primaryLabel: playbackService.primaryLabel
                orientationDegrees: settingsController.mirrorOrientationDegrees
                fillCrop: false
            }

            RowLayout {
                Layout.alignment: Qt.AlignLeft
                spacing: 12

                AppButton {
                    text: "Back to Gallery"
                    onClicked: appController.showGallery()
                }

                AppButton {
                    text: "Blackout Mirror"
                    onClicked: settingsController.blackoutMirror()
                }
            }
        }
    }

    Component {
        id: comparePage

        ColumnLayout {
            anchors.fill: parent
            spacing: 16

            MediaSurface {
                Layout.fillWidth: true
                Layout.fillHeight: true
                splitView: true
                primarySource: playbackService.primarySource
                secondarySource: playbackService.secondarySource
                primaryLabel: playbackService.primaryLabel
                secondaryLabel: playbackService.secondaryLabel
                fillCrop: settingsController.compareFillCrop
                orientationDegrees: settingsController.mirrorOrientationDegrees
            }

            RowLayout {
                spacing: 12

                AppButton {
                    text: "Back to Gallery"
                    onClicked: appController.showGallery()
                }

                Switch {
                    checked: settingsController.compareFillCrop
                    text: checked ? "Crop + Fit" : "Full Frame"
                    onToggled: settingsController.setCompareFillCrop(checked)
                }
            }
        }
    }

    Component {
        id: liveComparePage

        ColumnLayout {
            anchors.fill: parent
            spacing: 16

            MediaSurface {
                Layout.fillWidth: true
                Layout.fillHeight: true
                splitView: true
                primarySource: playbackService.primarySource
                secondarySource: playbackService.secondarySource
                primaryLabel: playbackService.primaryLabel
                secondaryLabel: playbackService.secondaryLabel
                fillCrop: settingsController.compareFillCrop
                orientationDegrees: settingsController.mirrorOrientationDegrees
                showGuides: true
            }

            RowLayout {
                spacing: 12

                AppButton {
                    text: "Back to Gallery"
                    onClicked: appController.showGallery()
                }

                Switch {
                    checked: settingsController.compareFillCrop
                    text: checked ? "Crop + Fit" : "Full Frame"
                    onToggled: settingsController.setCompareFillCrop(checked)
                }
            }
        }
    }

    Component {
        id: settingsPage

        Flickable {
            clip: true
            contentWidth: width
            contentHeight: settingsColumn.implicitHeight

            ColumnLayout {
                id: settingsColumn
                width: parent.width
                spacing: 18

                Rectangle {
                    Layout.fillWidth: true
                    radius: 28
                    color: "#f0e2d4"
                    border.width: 1
                    border.color: "#dbc7b6"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 14

                        Text {
                            text: "Display Assignment"
                            color: "#45372d"
                            font.family: "Noto Serif"
                            font.pixelSize: 28
                        }

                        RowLayout {
                            spacing: 12

                            ComboBox {
                                id: controlScreenCombo
                                model: settingsController.displays
                                textRole: "label"
                                currentIndex: Math.min(settingsController.controlScreenIndex, count - 1)
                                Layout.fillWidth: true
                            }

                            ComboBox {
                                id: mirrorScreenCombo
                                model: settingsController.displays
                                textRole: "label"
                                currentIndex: Math.min(settingsController.mirrorScreenIndex, count - 1)
                                Layout.fillWidth: true
                            }

                            AppButton {
                                text: "Apply"
                                onClicked: settingsController.saveScreenAssignment(controlScreenCombo.currentIndex, mirrorScreenCombo.currentIndex)
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 28
                    color: "#f6efe8"
                    border.width: 1
                    border.color: "#e2d5ca"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 14

                        Text {
                            text: "Mirror Preferences"
                            color: "#45372d"
                            font.family: "Noto Serif"
                            font.pixelSize: 28
                        }

                        RowLayout {
                            spacing: 10
                            Repeater {
                                model: [0, 90, 180, 270]
                                delegate: AppButton {
                                    text: "Rotate " + modelData + "°"
                                    onClicked: settingsController.setMirrorOrientation(modelData)
                                }
                            }
                        }

                        Switch {
                            checked: settingsController.compareFillCrop
                            text: checked ? "Compare uses crop + fit" : "Compare uses full frame"
                            onToggled: settingsController.setCompareFillCrop(checked)
                        }

                        RowLayout {
                            spacing: 12
                            AppButton {
                                text: "Show Test Pattern"
                                onClicked: settingsController.showMirrorTestPattern()
                            }
                            AppButton {
                                text: "Blackout Mirror"
                                onClicked: settingsController.blackoutMirror()
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 28
                    color: "#201915"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 14

                        Text {
                            text: "Camera Backend"
                            color: "#fbf6f0"
                            font.family: "Noto Serif"
                            font.pixelSize: 28
                        }

                        Repeater {
                            model: settingsController.cameraBackends

                            delegate: Rectangle {
                                required property var modelData
                                Layout.fillWidth: true
                                radius: 20
                                color: settingsController.cameraBackend === modelData.key ? "#3a2f27" : "#291f1a"
                                border.width: 1
                                border.color: modelData.available ? "#56473d" : "#6d3b36"
                                height: 64

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.margins: 14

                                    Text {
                                        text: modelData.label
                                        color: "#f8f1ea"
                                        font.family: "Noto Serif"
                                        font.pixelSize: 20
                                    }

                                    Item { Layout.fillWidth: true }

                                    Text {
                                        text: modelData.available ? "available" : "missing"
                                        color: modelData.available ? "#c4d8c3" : "#e8b8b0"
                                        font.family: "Noto Sans"
                                        font.pixelSize: 12
                                    }

                                    AppButton {
                                        text: "Use"
                                        enabled: modelData.available
                                        onClicked: settingsController.setCameraBackend(modelData.key)
                                    }
                                }
                            }
                        }

                        Text {
                            text: settingsController.dependencySummary
                            color: "#c6b7ab"
                            font.family: "Noto Sans"
                            font.pixelSize: 13
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }
        }
    }
}
