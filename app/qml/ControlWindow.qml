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
    color: "#f2ece7"

    readonly property bool navigationLocked: recordingController.isRecording || recordingController.hasReview || recordingController.countdown > 0
    readonly property bool portraitMirror: settingsController.mirrorOrientationDegrees === 90 || settingsController.mirrorOrientationDegrees === 270
    readonly property real cardWidth: Math.min(width * 0.82, 760)
    readonly property real wideCardWidth: Math.min(width * 0.94, 1080)
    readonly property real mediaCardWidth: Math.min(width * 0.94, 1180)
    readonly property string pageTitle: ({
        "dashboard": "Welcome to the Smart Choice!",
        "recording": "Record Your Look",
        "gallery": "Gallery",
        "player": playbackService.primaryLabel.length > 0 ? playbackService.primaryLabel : "Look Review",
        "compare": "Compare Looks",
        "live_compare": "Live Compare",
        "settings": "Settings"
    })[appController.currentPage] || "Smart Mirror"
    readonly property string pageSubtitle: ({
        "dashboard": "Choose a workflow and keep the mirror black until you need visual output.",
        "recording": recordingController.hasReview
                     ? "Review the recorded clip locally before saving it."
                     : (recordingController.isRecording
                        ? "The mirror is active for capture preview."
                        : "The mirror stays black until recording starts."),
        "gallery": "Review saved looks, compare them side by side, or start live compare.",
        "player": "Playback is active on the mirror while this local review stays on the control screen.",
        "compare": "Side-by-side comparison with mirror-aware crop mode.",
        "live_compare": "Compare a saved look with the current live preview.",
        "settings": "Adjust screen assignment, mirror orientation, and camera backend preferences."
    })[appController.currentPage] || ""

    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#f4ede7" }
            GradientStop { position: 0.45; color: "#ece2d8" }
            GradientStop { position: 1.0; color: "#f6f0eb" }
        }
    }

    Rectangle {
        width: parent.width * 0.42
        height: width
        radius: width / 2
        color: "#ffffff"
        opacity: 0.16
        x: -width * 0.18
        y: -height * 0.14
    }

    Rectangle {
        width: parent.width * 0.32
        height: width
        radius: width / 2
        color: "#d8c4b0"
        opacity: 0.18
        x: parent.width - width * 0.72
        y: parent.height - height * 0.74
    }

    Item {
        anchors.fill: parent

        Loader {
            id: pageLoader
            anchors.fill: parent
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

        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 18
            visible: appController.statusMessage.length > 0 || appController.errorMessage.length > 0
            radius: 999
            color: appController.errorMessage.length > 0 ? "#f7dbd6" : "#f1eae6"
            border.width: 1
            border.color: appController.errorMessage.length > 0 ? "#d89d94" : "#e4ddd7"
            width: Math.min(parent.width * 0.82, statusLabel.implicitWidth + 36)
            height: statusLabel.implicitHeight + 18
            z: 20

            Text {
                id: statusLabel
                anchors.centerIn: parent
                text: appController.errorMessage.length > 0 ? appController.errorMessage : appController.statusMessage
                color: appController.errorMessage.length > 0 ? "#7c2d26" : "#6b6661"
                font.family: "Noto Sans"
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                width: parent.width - 24
            }

            MouseArea {
                anchors.fill: parent
                enabled: appController.errorMessage.length > 0
                onClicked: appController.clearError()
            }
        }
    }

    Component {
        id: dashboardPage

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.centerIn: parent
                width: controlWindow.cardWidth
                spacing: 14

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: controlWindow.pageTitle
                    color: "#6b6661"
                    font.family: "Noto Serif"
                    font.pixelSize: 24
                    font.weight: Font.Medium
                    horizontalAlignment: Text.AlignHCenter
                }

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    radius: 999
                    color: "#f7f2ee"
                    border.width: 1
                    border.color: "#ebe0d7"
                    width: Math.min(controlWindow.cardWidth, sessionName.implicitWidth + 110)
                    height: sessionName.implicitHeight + 20

                    Text {
                        id: sessionName
                        anchors.centerIn: parent
                        text: sessionController.activeSessionName
                        color: "#7b756f"
                        font.family: "Noto Sans"
                        font.pixelSize: 13
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 30
                    color: "#f7f2ee"
                    border.width: 1
                    border.color: "#ffffff"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 28
                        spacing: 18

                        AppButton {
                            Layout.fillWidth: true
                            text: "Record Look"
                            onClicked: appController.showRecording()
                        }

                        AppButton {
                            Layout.fillWidth: true
                            text: "Gallery"
                            onClicked: appController.showGallery()
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            radius: 20
                            color: "#f1eae6"
                            border.width: 1
                            border.color: "#e4ddd7"

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 6
                                spacing: 8

                                Text {
                                    Layout.alignment: Qt.AlignHCenter
                                    text: "Mirror View: " + (controlWindow.portraitMirror ? "Portrait" : "Landscape") + " (" + settingsController.mirrorOrientationDegrees + "°)"
                                    color: "#7a746e"
                                    font.family: "Noto Sans"
                                    font.pixelSize: 12
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 42
                                        radius: 16
                                        color: controlWindow.portraitMirror ? "#e7ddd6" : "transparent"

                                        Text {
                                            anchors.centerIn: parent
                                            text: "Portrait"
                                            color: controlWindow.portraitMirror ? "#5e5650" : "#8a837e"
                                            font.family: "Noto Sans"
                                            font.pixelSize: 13
                                            font.weight: Font.DemiBold
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: settingsController.setMirrorOrientation(90)
                                        }
                                    }

                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 42
                                        radius: 16
                                        color: !controlWindow.portraitMirror ? "#e7ddd6" : "transparent"

                                        Text {
                                            anchors.centerIn: parent
                                            text: "Landscape"
                                            color: !controlWindow.portraitMirror ? "#5e5650" : "#8a837e"
                                            font.family: "Noto Sans"
                                            font.pixelSize: 13
                                            font.weight: Font.DemiBold
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: settingsController.setMirrorOrientation(0)
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: "Session ID: " + sessionController.activeSessionId
                            color: "#6a6661"
                            font.family: "Noto Sans"
                            font.pixelSize: 12
                            elide: Text.ElideMiddle
                        }
                    }
                }

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 12

                    Button {
                        text: "New Session"
                        flat: true
                        onClicked: sessionController.newSession("")

                        contentItem: Text {
                            text: parent.text
                            color: "#7d756f"
                            font.family: "Noto Sans"
                            font.pixelSize: 13
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }

                    Button {
                        text: "Settings"
                        flat: true
                        enabled: !controlWindow.navigationLocked
                        onClicked: appController.showSettings()

                        contentItem: Text {
                            text: parent.text
                            color: parent.enabled ? "#7d756f" : "#b8aea5"
                            font.family: "Noto Sans"
                            font.pixelSize: 13
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
            }
        }
    }

    Component {
        id: recordingPage

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 10

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: controlWindow.mediaCardWidth
                    Layout.fillWidth: true

                    ToolButton {
                        text: "‹"
                        enabled: !controlWindow.navigationLocked
                        onClicked: appController.showDashboard()
                    }

                    Text {
                        text: controlWindow.pageTitle
                        color: "#6b6661"
                        font.family: "Noto Serif"
                        font.pixelSize: 22
                        font.weight: Font.Medium
                    }

                    Item { Layout.fillWidth: true }

                    RowLayout {
                        spacing: 6

                        Repeater {
                            model: [0, 90, 180, 270]
                            delegate: AppButton {
                                text: modelData + "°"
                                implicitWidth: 72
                                enabled: !recordingController.isRecording && !recordingController.isBusy
                                onClicked: settingsController.setMirrorOrientation(modelData)
                            }
                        }
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: controlWindow.pageSubtitle
                    color: "#7d756f"
                    font.family: "Noto Sans"
                    font.pixelSize: 13
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    Layout.maximumWidth: controlWindow.mediaCardWidth
                }

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.maximumWidth: controlWindow.mediaCardWidth
                    radius: 30
                    color: "#f7f2ee"
                    border.width: 1
                    border.color: "#ffffff"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 22
                        spacing: 18

                        MediaSurface {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            primarySource: recordingController.hasReview ? recordingController.reviewSource : recordingController.previewSource
                            primaryLabel: recordingController.hasReview ? "Preview" : (recordingController.isRecording ? "Live" : "")
                            orientationDegrees: 0
                            showGuides: recordingController.isRecording
                            fillCrop: false
                        }

                        Rectangle {
                            Layout.alignment: Qt.AlignHCenter
                            radius: 24
                            color: "#f1eae6"
                            border.width: 1
                            border.color: "#e4ddd7"
                            width: timerText.implicitWidth + 34
                            height: timerText.implicitHeight + 14

                            Text {
                                id: timerText
                                anchors.centerIn: parent
                                text: recordingController.countdown > 0
                                      ? "Starting in " + recordingController.countdown
                                      : (recordingController.isRecording
                                         ? "Recording • " + recordingController.elapsedText
                                         : (recordingController.hasReview ? "Review captured look" : "Ready to record"))
                                color: recordingController.isRecording ? "#9e4b4b" : "#6b6661"
                                font.family: "Noto Serif"
                                font.pixelSize: 18
                            }
                        }

                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            visible: recordingController.errorMessage.length > 0
                            text: recordingController.errorMessage
                            color: "#9e4b4b"
                            font.family: "Noto Sans"
                            font.pixelSize: 13
                            wrapMode: Text.WordWrap
                            horizontalAlignment: Text.AlignHCenter
                            Layout.maximumWidth: parent.width * 0.75
                        }

                        RowLayout {
                            Layout.alignment: Qt.AlignHCenter
                            spacing: 12

                            AppButton {
                                text: "Start Recording"
                                enabled: !recordingController.isBusy && !recordingController.isRecording && !recordingController.hasReview
                                onClicked: recordingController.beginRecording()
                            }

                            AppButton {
                                text: "Stop"
                                enabled: recordingController.isRecording && !recordingController.isBusy
                                onClicked: recordingController.stopRecording()
                            }

                            AppButton {
                                text: "Save Video"
                                enabled: recordingController.hasReview && !recordingController.isBusy
                                onClicked: recordingController.saveRecording()
                            }

                            AppButton {
                                text: recordingController.hasReview ? "Discard" : "Cancel"
                                enabled: !recordingController.isBusy
                                onClicked: recordingController.discardRecording()
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: galleryPage

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 10

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    Layout.maximumWidth: controlWindow.wideCardWidth

                    ToolButton {
                        text: "‹"
                        enabled: !controlWindow.navigationLocked
                        onClicked: appController.showDashboard()
                    }

                    Text {
                        text: "Gallery"
                        color: "#6b6661"
                        font.family: "Noto Serif"
                        font.pixelSize: 22
                        font.weight: Font.Medium
                    }

                    Item { Layout.fillWidth: true }

                    Button {
                        text: "Clear"
                        flat: true
                        visible: galleryController.selectedIds.length > 0
                        onClicked: galleryController.clearSelection()

                        contentItem: Text {
                            text: parent.text
                            color: "#8c8681"
                            font.family: "Noto Sans"
                            font.pixelSize: 12
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.maximumWidth: controlWindow.wideCardWidth
                    radius: 30
                    color: "#f7f2ee"
                    border.width: 1
                    border.color: "#ffffff"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 26
                        spacing: 18

                        ListView {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 220
                            orientation: ListView.Horizontal
                            spacing: 14
                            clip: true
                            model: galleryController.videos

                            delegate: Item {
                                required property var modelData
                                width: 148
                                height: 200
                                readonly property bool selected: galleryController.selectedIds.indexOf(modelData.id) >= 0
                                readonly property int selectedIndex: galleryController.selectedIds.indexOf(modelData.id)

                                Rectangle {
                                    anchors.fill: parent
                                    radius: 16
                                    color: "#e5ded8"
                                    border.width: selected ? 2 : 0
                                    border.color: selected ? "#8e8077" : "transparent"

                                    Image {
                                        anchors.fill: parent
                                        anchors.margins: 0
                                        source: modelData.thumbnailUrl
                                        fillMode: Image.PreserveAspectCrop
                                        visible: source.toString().length > 0
                                        clip: true
                                    }

                                    Text {
                                        anchors.centerIn: parent
                                        visible: modelData.thumbnailUrl.length === 0
                                        text: "Look"
                                        color: "#8c8681"
                                        font.family: "Noto Serif"
                                        font.pixelSize: 18
                                    }

                                    Text {
                                        anchors.left: parent.left
                                        anchors.bottom: parent.bottom
                                        anchors.margins: 10
                                        text: modelData.title
                                        color: "#5f5a55"
                                        font.family: "Noto Sans"
                                        font.pixelSize: 12
                                    }

                                    Rectangle {
                                        anchors.right: parent.right
                                        anchors.bottom: parent.bottom
                                        anchors.margins: 10
                                        radius: 6
                                        color: "#88000000"
                                        width: durationLabel.implicitWidth + 12
                                        height: durationLabel.implicitHeight + 6

                                        Text {
                                            id: durationLabel
                                            anchors.centerIn: parent
                                            text: modelData.durationLabel
                                            color: "white"
                                            font.family: "Noto Sans"
                                            font.pixelSize: 10
                                            font.weight: Font.DemiBold
                                        }
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: galleryController.openVideo(modelData.id)
                                    }

                                    Rectangle {
                                        anchors.right: parent.right
                                        anchors.top: parent.top
                                        anchors.margins: 8
                                        width: 26
                                        height: 26
                                        radius: 8
                                        color: selected ? "#8e8077" : "#e7dfd8"

                                        Text {
                                            anchors.centerIn: parent
                                            text: selected ? (selectedIndex + 1).toString() : "+"
                                            color: selected ? "white" : "#6b6661"
                                            font.family: "Noto Sans"
                                            font.pixelSize: 12
                                            font.weight: Font.DemiBold
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: galleryController.toggleSelect(modelData.id)
                                        }
                                    }
                                }
                            }

                            Text {
                                anchors.centerIn: parent
                                visible: galleryController.videos.length === 0
                                text: "No looks recorded yet"
                                color: "#8c8681"
                                font.family: "Noto Sans"
                                font.pixelSize: 14
                            }
                        }

                        RowLayout {
                            Layout.alignment: Qt.AlignHCenter
                            spacing: 12

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
                                text: "Refresh"
                                onClicked: galleryController.refresh()
                            }

                            AppButton {
                                text: "Delete"
                                enabled: galleryController.selectedIds.length === 1
                                onClicked: galleryController.deleteVideo(galleryController.selectedIds[0])
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: playerPage

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 10

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    Layout.maximumWidth: controlWindow.mediaCardWidth

                    ToolButton {
                        text: "‹"
                        onClicked: appController.showGallery()
                    }

                    Text {
                        text: controlWindow.pageTitle
                        color: "#6b6661"
                        font.family: "Noto Serif"
                        font.pixelSize: 22
                        font.weight: Font.Medium
                    }
                }

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.maximumWidth: controlWindow.mediaCardWidth
                    radius: 30
                    color: "#f7f2ee"
                    border.width: 1
                    border.color: "#ffffff"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 22
                        spacing: 18

                        MediaSurface {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            primarySource: playbackService.primarySource
                            primaryLabel: playbackService.primaryLabel
                            orientationDegrees: settingsController.mirrorOrientationDegrees
                            fillCrop: false
                        }

                        RowLayout {
                            Layout.alignment: Qt.AlignHCenter
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
            }
        }
    }

    Component {
        id: comparePage

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 10

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    Layout.maximumWidth: controlWindow.mediaCardWidth

                    ToolButton {
                        text: "‹"
                        onClicked: appController.showGallery()
                    }

                    Text {
                        text: "Compare Looks"
                        color: "#6b6661"
                        font.family: "Noto Serif"
                        font.pixelSize: 22
                        font.weight: Font.Medium
                    }
                }

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.maximumWidth: controlWindow.mediaCardWidth
                    radius: 30
                    color: "#f7f2ee"
                    border.width: 1
                    border.color: "#ffffff"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 22
                        spacing: 18

                        MediaSurface {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            splitView: true
                            primarySource: playbackService.primarySource
                            secondarySource: playbackService.secondarySource
                            primaryLabel: "Look 1"
                            secondaryLabel: "Look 2"
                            fillCrop: settingsController.compareFillCrop
                            orientationDegrees: settingsController.mirrorOrientationDegrees
                        }

                        RowLayout {
                            Layout.alignment: Qt.AlignHCenter
                            spacing: 12

                            AppButton {
                                text: "Back to Gallery"
                                onClicked: appController.showGallery()
                            }

                            AppButton {
                                text: settingsController.compareFillCrop ? "Crop + Fit" : "Full Frame"
                                onClicked: settingsController.setCompareFillCrop(!settingsController.compareFillCrop)
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: liveComparePage

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 10

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    Layout.maximumWidth: controlWindow.mediaCardWidth

                    ToolButton {
                        text: "‹"
                        onClicked: appController.showGallery()
                    }

                    Text {
                        text: "Live Compare"
                        color: "#6b6661"
                        font.family: "Noto Serif"
                        font.pixelSize: 22
                        font.weight: Font.Medium
                    }
                }

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.maximumWidth: controlWindow.mediaCardWidth
                    radius: 30
                    color: "#f7f2ee"
                    border.width: 1
                    border.color: "#ffffff"

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 22
                        spacing: 18

                        MediaSurface {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            splitView: true
                            primarySource: playbackService.primarySource
                            secondarySource: playbackService.secondarySource
                            primaryLabel: "Look 1"
                            secondaryLabel: "Live"
                            fillCrop: settingsController.compareFillCrop
                            orientationDegrees: settingsController.mirrorOrientationDegrees
                            showGuides: true
                        }

                        RowLayout {
                            Layout.alignment: Qt.AlignHCenter
                            spacing: 12

                            AppButton {
                                text: "Back to Gallery"
                                onClicked: appController.showGallery()
                            }

                            AppButton {
                                text: settingsController.compareFillCrop ? "Crop + Fit" : "Full Frame"
                                onClicked: settingsController.setCompareFillCrop(!settingsController.compareFillCrop)
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: settingsPage

        Item {
            anchors.fill: parent

            ScrollView {
                anchors.fill: parent
                anchors.margins: 20
                clip: true

                ColumnLayout {
                    width: controlWindow.wideCardWidth
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 14

                    RowLayout {
                        Layout.fillWidth: true

                        ToolButton {
                            text: "‹"
                            enabled: !controlWindow.navigationLocked
                            onClicked: appController.showDashboard()
                        }

                        Text {
                            text: "Settings"
                            color: "#6b6661"
                            font.family: "Noto Serif"
                            font.pixelSize: 22
                            font.weight: Font.Medium
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        radius: 30
                        color: "#f7f2ee"
                        border.width: 1
                        border.color: "#ffffff"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            Text {
                                text: "Display Assignment"
                                color: "#6b6661"
                                font.family: "Noto Serif"
                                font.pixelSize: 24
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                ComboBox {
                                    id: controlScreenCombo
                                    Layout.fillWidth: true
                                    model: settingsController.displays
                                    textRole: "label"
                                    currentIndex: Math.min(settingsController.controlScreenIndex >= 0 ? settingsController.controlScreenIndex : 0, Math.max(0, count - 1))
                                }

                                ComboBox {
                                    id: mirrorScreenCombo
                                    Layout.fillWidth: true
                                    model: settingsController.displays
                                    textRole: "label"
                                    currentIndex: Math.min(settingsController.mirrorScreenIndex >= 0 ? settingsController.mirrorScreenIndex : Math.max(0, count - 1), Math.max(0, count - 1))
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
                        radius: 30
                        color: "#f7f2ee"
                        border.width: 1
                        border.color: "#ffffff"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 16

                            Text {
                                text: "Mirror Preferences"
                                color: "#6b6661"
                                font.family: "Noto Serif"
                                font.pixelSize: 24
                            }

                            RowLayout {
                                spacing: 10
                                Repeater {
                                    model: [0, 90, 180, 270]
                                    delegate: AppButton {
                                        text: modelData + "°"
                                        onClicked: settingsController.setMirrorOrientation(modelData)
                                    }
                                }
                            }

                            RowLayout {
                                spacing: 12

                                AppButton {
                                    text: settingsController.compareFillCrop ? "Compare: Crop + Fit" : "Compare: Full Frame"
                                    onClicked: settingsController.setCompareFillCrop(!settingsController.compareFillCrop)
                                }

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
                        radius: 30
                        color: "#f7f2ee"
                        border.width: 1
                        border.color: "#ffffff"

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 24
                            spacing: 14

                            Text {
                                text: "Camera Backend"
                                color: "#6b6661"
                                font.family: "Noto Serif"
                                font.pixelSize: 24
                            }

                            Repeater {
                                model: settingsController.cameraBackends

                                delegate: Rectangle {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    radius: 20
                                    color: settingsController.cameraBackend === modelData.key ? "#f1eae6" : "#fbf7f3"
                                    border.width: 1
                                    border.color: modelData.available ? "#e4ddd7" : "#d9b7b3"
                                    implicitHeight: 64

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14

                                        Text {
                                            text: modelData.label
                                            color: "#6b6661"
                                            font.family: "Noto Serif"
                                            font.pixelSize: 18
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: modelData.available ? "available" : "missing"
                                            color: modelData.available ? "#7a746e" : "#9e4b4b"
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
                                color: "#7a746e"
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
}
