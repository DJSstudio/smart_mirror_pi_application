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
            title: recordingController.hasReview   ? "Review Your Look"
                 : recordingController.isRecording  ? "Recording…"
                 :                                    "Record a Look"
            subtitle: recordingController.hasReview
                    ? "Watch the clip, then save it or discard it."
                    : (recordingController.isRecording
                        ? "Live preview is on the mirror. Press Stop when done."
                        : "Press Start — a 5-second countdown will begin.")
            showBack: !recordingController.isRecording
                      && !recordingController.hasReview
                      && recordingController.countdown === 0
            onBackClicked: appController.showDashboard()
        }

        // ── Preview / review surface ─────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 20
            color: "#0D0B09"
            border.width: 1
            border.color: "#1C1917"
            clip: true

            // Live preview
            MediaPlayer {
                id: livePlayer
                source: recordingController.previewSource
                loops: MediaPlayer.Infinite
                videoOutput: liveOutput
                audioOutput: AudioOutput { muted: true }
                onSourceChanged: { if (source.toString().length > 0) play(); else stop() }
            }

            VideoOutput {
                id: liveOutput
                anchors.fill: parent
                fillMode: VideoOutput.PreserveAspectFit
                visible: recordingController.previewSource.length > 0
            }

            // Review player
            MediaPlayer {
                id: reviewPlayer
                source: recordingController.reviewSource
                loops: MediaPlayer.Infinite
                videoOutput: reviewOutput
                audioOutput: AudioOutput { muted: false; volume: 0.85 }
                onSourceChanged: { if (source.toString().length > 0) play(); else stop() }
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

            // Idle placeholder — shown before recording starts
            ColumnLayout {
                anchors.centerIn: parent
                visible: !recordingController.isRecording
                         && !recordingController.hasReview
                         && recordingController.countdown === 0
                spacing: 14

                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    width: 72; height: 72; radius: 999
                    color: "#1C1917"

                    Text {
                        anchors.centerIn: parent
                        text: "⏺"
                        font.pixelSize: 30
                        color: "#C4956A"
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Press Start to begin recording"
                    font.pixelSize: 16
                    color: "#6B635C"
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: recordingController.backendLabel.length > 0
                          ? recordingController.backendLabel
                          : "No camera detected"
                    font.pixelSize: 12
                    color: "#4A4540"
                }
            }

            // "Look at the mirror" prompt — shown during countdown and recording
            ColumnLayout {
                anchors.centerIn: parent
                visible: (recordingController.isRecording || recordingController.countdown > 0)
                         && !recordingController.hasReview
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
                    text: "Look at the mirror to see yourself"
                    font.pixelSize: 20
                    font.weight: Font.Medium
                    color: "#C4956A"
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Live preview is on the mirror display"
                    font.pixelSize: 14
                    color: "#6B635C"
                }
            }

            // REC badge
            Rectangle {
                visible: recordingController.isRecording
                anchors { top: parent.top; right: parent.right; margins: 16 }
                radius: 999
                width: _recRow.implicitWidth + 16; height: 32
                color: "#CC8B2E2E"

                RowLayout {
                    id: _recRow
                    anchors.centerIn: parent
                    spacing: 8

                    Rectangle {
                        width: 10; height: 10; radius: 999
                        color: "#FF6B6B"

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
                        color: "#FFFFFF"
                    }
                }
            }
        }

        // ── Error banner ─────────────────────────────────────────────
        Rectangle {
            Layout.fillWidth: true
            visible: recordingController.errorMessage.length > 0
            height: 44; radius: 12
            color: "#8B2E2E"

            Text {
                anchors { fill: parent; leftMargin: 16; rightMargin: 16 }
                verticalAlignment: Text.AlignVCenter
                text: "⚠  " + recordingController.errorMessage
                color: "#FFFFFF"
                font.pixelSize: 13
                elide: Text.ElideRight
            }
        }

        // ── Action buttons ───────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            // Idle → Start
            AppButton {
                visible: !recordingController.isRecording
                         && !recordingController.hasReview
                         && recordingController.countdown === 0
                Layout.fillWidth: true
                implicitHeight: 60
                text: "Start Recording"
                enabled: !recordingController.isBusy
                onClicked: recordingController.beginRecording()
            }

            // Active → Stop
            AppButton {
                visible: recordingController.isRecording
                Layout.fillWidth: true
                implicitHeight: 60
                text: recordingController.isBusy ? "Stopping…" : "Stop Recording"
                variant: "danger"
                enabled: !recordingController.isBusy
                onClicked: recordingController.stopRecording()
            }

            // Review → Save
            AppButton {
                visible: recordingController.hasReview
                Layout.fillWidth: true
                implicitHeight: 60
                text: "Save Look"
                enabled: !recordingController.isBusy
                onClicked: recordingController.saveRecording()
            }

            // Review / recording → Discard
            AppButton {
                visible: recordingController.hasReview
                         || recordingController.isRecording
                         || recordingController.countdown > 0
                implicitHeight: 60
                implicitWidth: 160
                text: "Discard"
                variant: "secondary"
                enabled: !recordingController.isBusy
                onClicked: recordingController.discardRecording()
            }
        }
    }
}
