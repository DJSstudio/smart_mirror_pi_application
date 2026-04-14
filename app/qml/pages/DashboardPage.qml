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

            // Settings button — top-right corner
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

            // Record a Look — primary CTA (inverted, charcoal)
            HeroTile {
                Layout.fillWidth: true
                Layout.fillHeight: true
                icon: "⏺"
                label: "Record a Look"
                description: "5-second countdown, then capture"
                inverted: true
                onTapped: appController.showRecording()
            }

            // My Looks — gallery
            HeroTile {
                Layout.fillWidth: true
                Layout.fillHeight: true
                icon: "▦"
                label: "My Looks"
                description: sessionController && sessionController.videoCount > 0
                    ? sessionController.videoCount + " look"
                      + (sessionController.videoCount === 1 ? "" : "s") + " ready to compare"
                    : "No looks recorded yet"
                enabled: sessionController ? sessionController.videoCount > 0 : false
                onTapped: {
                    if (galleryController) galleryController.refresh()
                    appController.showGallery()
                }
            }
        }

        // ── Action tiles row ─────────────────────────────────────────
        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            // Share to Phone
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

            // End Session / Switch User
            ActionTile {
                Layout.fillWidth: true
                icon: "⏏"
                label: "New Session"
                description: "Scan QR to switch user or start fresh"
                onTapped: loginController.startLogin()
            }
        }
    }

    // ── HeroTile — large primary action card ──────────────────────────
    component HeroTile: Rectangle {
        id: _hero

        property string icon: ""
        property string label: ""
        property string description: ""
        property bool inverted: false

        signal tapped()

        radius: 20
        color: !_hero.enabled          ? "#F0EBE5"
             : _hero.inverted          ? (_hMa.containsMouse ? "#2E2A27" : "#1C1917")
             : _hMa.containsMouse      ? "#F5F0EA"
             :                           "#FFFFFF"
        border.width: _hero.inverted ? 0 : 1
        border.color: "#E8E2DC"

        Behavior on color { ColorAnimation { duration: 120 } }

        ColumnLayout {
            anchors { fill: parent; margins: 28 }
            spacing: 0

            // Icon circle
            Rectangle {
                width: 64; height: 64; radius: 999
                color: _hero.inverted ? "#2E2A27"
                     : !_hero.enabled ? "#E8E2DC"
                     :                  "#F0EBE5"

                Text {
                    anchors.centerIn: parent
                    text: _hero.icon
                    font.pixelSize: 28
                    color: _hero.inverted ? "#C4956A"
                         : !_hero.enabled ? "#B0A89E"
                         :                  "#1C1917"
                }
            }

            Item { Layout.fillHeight: true }

            Text {
                text: _hero.label
                font.pixelSize: 22
                font.weight: Font.Bold
                color: _hero.inverted ? "#FFFFFF"
                     : !_hero.enabled ? "#B0A89E"
                     :                  "#1C1917"
            }

            Item { Layout.preferredHeight: 6 }

            Text {
                Layout.fillWidth: true
                text: _hero.description
                font.pixelSize: 13
                color: _hero.inverted ? "#9A9088"
                     : !_hero.enabled ? "#C4BCBA"
                     :                  "#6B6560"
                wrapMode: Text.WordWrap
            }
        }

        MouseArea {
            id: _hMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: _hero.enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
            enabled: _hero.enabled
            onClicked: _hero.tapped()
        }
    }

    // ── ActionTile — smaller secondary action card ────────────────────
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

            // Icon
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

            // Text
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

            // Chevron
            Text {
                text: "›"
                font.pixelSize: 22
                color: _action.enabled ? "#C4956A" : "#D8D4D0"
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
