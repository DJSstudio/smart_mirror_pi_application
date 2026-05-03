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
            id: surface
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 20
            color: "#0D0B09"
            border.width: 1
            border.color: "#1C1917"
            clip: true

            // Subtle gold radial glow during countdown/recording for warmth
            Rectangle {
                anchors.fill: parent
                radius: 20
                visible: recordingController.isRecording || recordingController.countdown > 0
                gradient: Gradient {
                    orientation: Gradient.Vertical
                    GradientStop { position: 0.0; color: "#1A140E" }
                    GradientStop { position: 0.6; color: "#0D0B09" }
                    GradientStop { position: 1.0; color: "#0D0B09" }
                }
            }

            // ── Review player (only when reviewing a finished clip) ──
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

            // ── State 1: Idle ────────────────────────────────────────
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

            // ── State 2: Recording (after countdown ends) ────────────
            ColumnLayout {
                anchors.centerIn: parent
                visible: recordingController.isRecording
                         && recordingController.countdown === 0
                         && !recordingController.hasReview
                spacing: 24

                // Mirror disc — gold ring for "now recording" warmth
                Item {
                    Layout.alignment: Qt.AlignHCenter
                    width: 120; height: 120

                    Rectangle {
                        anchors.centerIn: parent
                        width: 120; height: 120; radius: 999
                        color: "transparent"
                        border.width: 2
                        border.color: "#C4956A"
                        opacity: 0.3
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        width: 96; height: 96; radius: 999
                        color: "#1C1917"

                        Text {
                            anchors.centerIn: parent
                            text: "🪞"
                            font.pixelSize: 44
                        }
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Look at the mirror"
                    font.pixelSize: 24
                    font.weight: Font.Medium
                    color: "#E8DCCB"
                }

                // Elapsed time — large, clear
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: recordingController.elapsedText
                    font.family: "Noto Sans Mono, Consolas, monospace"
                    font.pixelSize: 38
                    font.weight: Font.Light
                    color: "#C4956A"
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: "Tap Stop when you are done"
                    font.pixelSize: 13
                    color: "#6B635C"
                }
            }

            // ── State 3: Countdown — overlay on top, hides everything else
            // Drawn LAST so it's visually on top.  Solid backdrop blocks the
            // recording/idle panels behind it so nothing competes for the
            // user's attention with the countdown number.
            Rectangle {
                id: countdownLayer
                anchors.fill: parent
                radius: 20
                visible: recordingController.countdown > 0
                color: "#E60D0B09"  // 90% opaque

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 24

                    // Big numeral — the focus
                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: recordingController.countdown.toString()
                        font.family: "Noto Serif, Georgia, serif"
                        font.pixelSize: 160
                        font.weight: Font.Light
                        color: "#FFF8F4"
                        opacity: 0.95

                        SequentialAnimation on scale {
                            running: recordingController.countdown > 0
                            loops: Animation.Infinite
                            NumberAnimation { to: 1.18; duration: 280; easing.type: Easing.OutQuad }
                            NumberAnimation { to: 1.0;  duration: 720; easing.type: Easing.InOutQuad }
                        }
                    }

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "Get ready"
                        font.pixelSize: 18
                        font.weight: Font.Light
                        color: "#C4956A"
                        opacity: 0.85
                    }

                    Item { Layout.preferredHeight: 24 }   // spacer

                    Text {
                        Layout.alignment: Qt.AlignHCenter
                        text: "🪞  Look at the mirror"
                        font.pixelSize: 14
                        color: "#9A8F84"
                    }
                }
            }

            // ── REC badge (top-right corner, only during real recording) ──
            Rectangle {
                visible: recordingController.isRecording && recordingController.countdown === 0
                anchors { top: parent.top; right: parent.right; margins: 16 }
                radius: 999
                width: _recRow.implicitWidth + 18; height: 32
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
                        text: "REC"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        font.letterSpacing: 1
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
