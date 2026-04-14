// Dashboard — primary landing screen for retail customers.
import QtQuick
import QtQuick.Layouts

Item {
    id: root

    ColumnLayout {
        anchors { fill: parent; margins: 28 }
        spacing: 16

        // ── Header row ───────────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 0

            ColumnLayout {
                spacing: 4

                Text {
                    text: "Smart Mirror"
                    font.family: "Noto Serif, Georgia, serif"
                    font.pixelSize: 30
                    font.weight: Font.Medium
                    color: "#1C1917"
                }

                Text {
                    text: sessionController
                        ? (sessionController.hasActiveSession
                            ? (sessionController.videoCount + " look"
                               + (sessionController.videoCount === 1 ? "" : "s") + " saved")
                            : "Welcome")
                        : ""
                    font.pixelSize: 14
                    color: "#A09890"
                }
            }

            Item { Layout.fillWidth: true }

            // Settings button
            Rectangle {
                width: 44; height: 44; radius: 999
                color: _settingsMa.containsMouse ? "#EDE8E3" : "#F0EBE5"
                border.width: 1; border.color: "#D8D0C8"

                Text {
                    anchors.centerIn: parent
                    text: "⚙"
                    font.pixelSize: 20
                    color: "#6B6560"
                }

                MouseArea {
                    id: _settingsMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: appController.showSettings()
                }
            }
        }

        // ── Hero tiles row ───────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            // ── Record a Look ─────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 20
                color: _recMa.containsMouse ? "#2E2A27" : "#1C1917"
                clip: true

                Behavior on color { ColorAnimation { duration: 120 } }

                ColumnLayout {
                    anchors { fill: parent; margins: 28 }
                    spacing: 0

                    // Session stat chip — top left
                    Rectangle {
                        visible: sessionController && sessionController.videoCount > 0
                        radius: 999
                        color: "#2E2A27"
                        width: _statTxt.implicitWidth + 16; height: 28

                        Text {
                            id: _statTxt
                            anchors.centerIn: parent
                            text: (sessionController ? sessionController.videoCount : 0)
                                  + " look" + (sessionController && sessionController.videoCount === 1 ? "" : "s") + " this session"
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: "#C4956A"
                        }
                    }

                    Item { Layout.fillHeight: true }

                    // Icon circle
                    Rectangle {
                        width: 64; height: 64; radius: 999
                        color: "#2E2A27"

                        Text {
                            anchors.centerIn: parent
                            text: "⏺"
                            font.pixelSize: 28
                            color: "#C4956A"
                        }
                    }

                    Item { Layout.preferredHeight: 16 }

                    Text {
                        text: "Record a Look"
                        font.pixelSize: 22
                        font.weight: Font.Bold
                        color: "#FFFFFF"
                    }

                    Item { Layout.preferredHeight: 6 }

                    Text {
                        Layout.fillWidth: true
                        text: "5-second countdown, then capture"
                        font.pixelSize: 13
                        color: "#9A9088"
                        wrapMode: Text.WordWrap
                    }
                }

                MouseArea {
                    id: _recMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: appController.showRecording()
                }
            }

            // ── My Looks ──────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 20
                color: "#FFFFFF"
                border.width: 1
                border.color: "#E8E2DC"
                clip: true

                // ── With thumbnail (looks exist) ──────────────────────
                Item {
                    anchors.fill: parent
                    visible: galleryController && galleryController.videoCount > 0

                    // Latest look thumbnail as full-bleed background
                    Image {
                        id: _latestThumb
                        anchors.fill: parent
                        source: (galleryController && galleryController.videos
                                 && galleryController.videos.length > 0)
                                ? galleryController.videos[0].thumbnailUrl : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true

                        // Subtle scale on hover
                        scale: _looksMa.containsMouse ? 1.04 : 1.0
                        Behavior on scale { NumberAnimation { duration: 300; easing.type: Easing.OutQuad } }
                    }

                    // Gradient overlay — lighter at top, darker at bottom for text
                    Rectangle {
                        anchors.fill: parent
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: "#55000000" }
                            GradientStop { position: 0.5; color: "#22000000" }
                            GradientStop { position: 1.0; color: "#CC000000" }
                        }
                    }

                    // Look count badge — top left
                    Rectangle {
                        anchors { top: parent.top; left: parent.left; margins: 20 }
                        radius: 999
                        color: "#CC000000"
                        width: _cntTxt.implicitWidth + 16; height: 28

                        Text {
                            id: _cntTxt
                            anchors.centerIn: parent
                            text: (galleryController ? galleryController.videoCount : 0)
                                  + " look" + (galleryController && galleryController.videoCount === 1 ? "" : "s")
                            font.pixelSize: 12
                            font.weight: Font.Medium
                            color: "#FFFFFF"
                        }
                    }

                    // Latest look title badge — top right
                    Rectangle {
                        anchors { top: parent.top; right: parent.right; margins: 20 }
                        radius: 6
                        color: "#CC000000"
                        width: Math.min(_latestLbl.implicitWidth + 14, 140); height: 28
                        clip: true

                        Text {
                            id: _latestLbl
                            anchors.centerIn: parent
                            width: parent.width - 14
                            text: (galleryController && galleryController.videos
                                   && galleryController.videos.length > 0)
                                  ? galleryController.videos[0].title : ""
                            font.pixelSize: 12
                            color: "#FFFFFF"
                            elide: Text.ElideRight
                        }
                    }

                    // Bottom text overlay
                    ColumnLayout {
                        anchors {
                            left: parent.left; right: parent.right
                            bottom: parent.bottom; margins: 24
                        }
                        spacing: 4

                        Text {
                            text: "My Looks"
                            font.pixelSize: 22
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }

                        Text {
                            text: "Tap to review, compare or export"
                            font.pixelSize: 13
                            color: "#CCE8E2DC"
                        }
                    }
                }

                // ── Empty state (no looks yet) ────────────────────────
                ColumnLayout {
                    anchors { fill: parent; margins: 28 }
                    visible: !galleryController || galleryController.videoCount === 0
                    spacing: 0

                    Rectangle {
                        width: 64; height: 64; radius: 999
                        color: "#F0EBE5"

                        Text {
                            anchors.centerIn: parent
                            text: "▦"
                            font.pixelSize: 28
                            color: "#C4BCBA"
                        }
                    }

                    Item { Layout.fillHeight: true }

                    Text {
                        text: "My Looks"
                        font.pixelSize: 22
                        font.weight: Font.Bold
                        color: "#B0A89E"
                    }

                    Item { Layout.preferredHeight: 6 }

                    Text {
                        Layout.fillWidth: true
                        text: "Record your first look to see it here"
                        font.pixelSize: 13
                        color: "#C4BCBA"
                        wrapMode: Text.WordWrap
                    }
                }

                MouseArea {
                    id: _looksMa
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: galleryController && galleryController.videoCount > 0
                                 ? Qt.PointingHandCursor : Qt.ArrowCursor
                    enabled: galleryController && galleryController.videoCount > 0
                    onClicked: {
                        if (galleryController) galleryController.refresh()
                        appController.showGallery()
                    }
                }
            }
        }

        // ── Action tiles row ─────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            ActionTile {
                Layout.fillWidth: true
                icon: "📱"
                label: "Share to Phone"
                description: "Browse & download recordings"
                enabled: sessionController ? sessionController.videoCount > 0 : false
                onTapped: {
                    if (galleryController) galleryController.refresh()
                    exportController.showSessionQr()
                }
            }

            ActionTile {
                Layout.fillWidth: true
                icon: "⏏"
                label: "New Session"
                description: "Scan QR to switch user or start fresh"
                onTapped: loginController.startLogin()
            }
        }
    }

    // ── ActionTile ────────────────────────────────────────────────────
    component ActionTile: Rectangle {
        id: _action

        property string icon: ""
        property string label: ""
        property string description: ""

        signal tapped()

        implicitHeight: 100
        radius: 16
        color: !_action.enabled   ? "#F5F2EF"
             : _aMa.containsMouse ? "#F5F0EA"
             :                      "#FFFFFF"
        border.width: 1
        border.color: "#E8E2DC"

        Behavior on color { ColorAnimation { duration: 100 } }

        RowLayout {
            anchors { fill: parent; margins: 20 }
            spacing: 16

            Rectangle {
                width: 48; height: 48; radius: 12
                color: _action.enabled ? "#F0EBE5" : "#ECEAE7"

                Text {
                    anchors.centerIn: parent
                    text: _action.icon
                    font.pixelSize: 22
                    color: _action.enabled ? "#1C1917" : "#C4BCBA"
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 3

                Text {
                    text: _action.label
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    color: _action.enabled ? "#1C1917" : "#B0A89E"
                }

                Text {
                    Layout.fillWidth: true
                    text: _action.description
                    font.pixelSize: 12
                    color: _action.enabled ? "#6B6560" : "#C4BCBA"
                    wrapMode: Text.WordWrap
                }
            }

            Text {
                text: "›"
                font.pixelSize: 22
                color: "#C4956A"
                visible: _action.enabled
            }
        }

        MouseArea {
            id: _aMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: _action.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            enabled: _action.enabled
            onClicked: _action.tapped()
        }
    }
}
