// Recording page — countdown → live capture → review → save/discard.
import QtQuick
import QtQuick.Layouts
import QtMultimedia
import "../components"

Item {
    id: root

    ColumnLayout {
        anchors { fill: parent; margins: 24 }
        spacing: 16

        // ── Header ──────────────────────────────────────────────────
        PageHeader {
            Layout.fillWidth: true
            title: recordingController.hasReview
                    ? "Review Your Look"
                    : (recordingController.isRecording ? "Recording…" : "Record a Look")
            subtitle: recordingController.hasReview
                    ? "Watch the clip, then save it to your gallery or discard it."
                    : (recordingController.isRecording
                        ? "The mirror is showing the live preview. Press Stop when done."
                        : "When you press Start, a 5-second countdown will begin.")
            showBack: !recordingController.isRecording && !recordingController.hasReview && recordingController.countdown === 0
            onBackClicked: appController.showDashboard()
        }

        // ── Preview / review surface ────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 20
            color: "#0d0b09"
            border.width: 1
            border.color: "#1c1814"
            clip: true

            // Live preview (UDP stream during recording / countdown)
            MediaPlayer {
                id: livePlayer
                source: recordingController.previewSource
                loops: MediaPlayer.Infinite
                videoOutput: liveOutput
                audioOutput: AudioOutput { muted: true }
                onSourceChanged: {
                    if (source.toString().length > 0) play()
                    else stop()
                }
            }

            VideoOutput {
                id: liveOutput
                anchors.fill: parent
                fillMode: VideoOutput.PreserveAspectFit
                visible: recordingController.previewSource.length > 0
            }

            // Post-stop review player
            MediaPlayer {
                id: reviewPlayer
                source: recordingController.reviewSource
                loops: MediaPlayer.Infinite
                videoOutput: reviewOutput
                audioOutput: AudioOutput { muted: false; volume: 0.85 }

                onSourceChanged: {
                    if (source.toString().length > 0) play()
                    else stop()
                }
            }

            VideoOutput {
                id: reviewOutput
                anchors.fill: parent
                fillMode: VideoOutput.PreserveAspectFit
                visible: recordingController.reviewSource.length > 0
            }

            // Countdown overlay
            CountdownOverlay {
                anchors.fill: parent
                count: recordingController.countdown
            }

            // Idle placeholder
            ColumnLayout {
                anchors.centerIn: parent
                visible: !recordingController.isRecording
                         && !recordingController.hasReview
                         && recordingController.countdown === 0
                         && recordingController.previewSource.length === 0
                spacing: 12

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "⏺"
                    font.pixelSize: 48
                    color: "#5a504a"
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Camera preview will appear here"
                    font.pixelSize: 15
                    color: "#7a746e"
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: recordingController.backendLabel.length > 0
                          ? "Backend: " + recordingController.backendLabel
                          : "No camera detected"
                    font.pixelSize: 12
                    color: "#9d9590"
                }
            }

            // Recording indicator
            Rectangle {
                visible: recordingController.isRecording
                anchors { top: parent.top; right: parent.right; margins: 14 }
                radius: 999
                width: recRow.implicitWidth + 14
                height: 28
                color: "#aa8c2222"

                RowLayout {
                    id: recRow
                    anchors.centerIn: parent
                    spacing: 6

                    Rectangle {
                        width: 10; height: 10; radius: 999
                        color: "#e05050"

                        SequentialAnimation on opacity {
                            running: recordingController.isRecording
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.2; duration: 600 }
                            NumberAnimation { to: 1.0; duration: 600 }
                        }
                    }

                    Text {
                        text: "REC  " + recordingController.elapsedText
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                        color: "#fff0ee"
                    }
                }
            }
        }

        // ── Error banner ────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            visible: recordingController.errorMessage.length > 0
            height: 38
            radius: 10
            color: "#7a2c2c"

            Text {
                anchors { fill: parent; leftMargin: 14; rightMargin: 14 }
                verticalAlignment: Text.AlignVCenter
                text: "⚠  " + recordingController.errorMessage
                color: "#fff0ee"
                font.pixelSize: 13
                elide: Text.ElideRight
            }
        }

        // ── Action buttons ──────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            // Idle state
            AppButton {
                visible: !recordingController.isRecording
                         && !recordingController.hasReview
                         && recordingController.countdown === 0
                Layout.fillWidth: true
                text: "Start Recording"
                enabled: !recordingController.isBusy
                onClicked: recordingController.beginRecording()
            }

            // Recording active
            AppButton {
                visible: recordingController.isRecording
                Layout.fillWidth: true
                text: "Stop Recording"
                variant: "danger"
                onClicked: recordingController.stopRecording()
            }

            // Review state
            AppButton {
                visible: recordingController.hasReview
                Layout.fillWidth: true
                text: "Save Look"
                enabled: !recordingController.isBusy
                onClicked: recordingController.saveRecording()
            }

            AppButton {
                visible: recordingController.hasReview
                         || recordingController.isRecording
                         || recordingController.countdown > 0
                Layout.fillWidth: true
                text: "Discard"
                variant: "secondary"
                enabled: !recordingController.isBusy
                onClicked: recordingController.discardRecording()
            }
        }
    }
}
