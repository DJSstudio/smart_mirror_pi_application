// Dashboard / home screen — entry point after boot.
// Mirror stays black. User picks a workflow.
import QtQuick
import QtQuick.Layouts
import "../components"

Item {
    id: root

    ColumnLayout {
        anchors { fill: parent; margins: 32 }
        spacing: 0

        // ── Header ──────────────────────────────────────────────────
        Item { Layout.fillHeight: true; Layout.maximumHeight: 24 }

        Text {
            text: "Smart Mirror"
            font.family: "Noto Serif, Georgia, serif"
            font.pixelSize: 32
            font.weight: Font.Medium
            color: "#3c3530"
        }

        Item { Layout.preferredHeight: 4 }

        Text {
            text: sessionController.hasActiveSession
                ? ("Session active  ·  " + sessionController.videoCount + " look"
                   + (sessionController.videoCount === 1 ? "" : "s"))
                : "No active session"
            font.pixelSize: 14
            color: "#8c8681"
        }

        Item { Layout.fillHeight: true; Layout.maximumHeight: 40 }

        // ── Workflow cards ───────────────────────────────────────────
        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: 16
            rowSpacing: 16

            // Record
            WorkflowCard {
                Layout.fillWidth: true
                icon: "⏺"
                label: "Record Look"
                description: "Capture a new look with the camera"
                onTapped: appController.showRecording()
            }

            // Gallery
            WorkflowCard {
                Layout.fillWidth: true
                icon: "▦"
                label: "Gallery"
                description: "Review, compare or play saved looks"
                enabled: sessionController.videoCount > 0
                onTapped: { galleryController.refresh(); appController.showGallery() }
            }

            // New session
            WorkflowCard {
                Layout.fillWidth: true
                icon: "＋"
                label: "New Session"
                description: "Start a fresh session"
                onTapped: { sessionController.newSession(); galleryController.refresh() }
            }

            // Settings
            WorkflowCard {
                Layout.fillWidth: true
                icon: "⚙"
                label: "Settings"
                description: "Configure camera, screens and display"
                onTapped: appController.showSettings()
            }
        }

        Item { Layout.fillHeight: true }

        // ── Footer hint ──────────────────────────────────────────────
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: "Mirror display stays black until a workflow activates it."
            font.pixelSize: 12
            color: "#aaa5a0"
        }

        Item { Layout.preferredHeight: 16 }
    }

    // ── WorkflowCard component ────────────────────────────────────────
    component WorkflowCard: Rectangle {
        id: card

        property string icon: ""
        property string label: ""
        property string description: ""

        signal tapped()

        implicitHeight: 110
        radius: 20
        color: cardMa.containsMouse ? "#ede5de" : "#f4ede8"
        border.width: 1
        border.color: "#d6cdc5"

        Behavior on color { ColorAnimation { duration: 100 } }

        ColumnLayout {
            anchors { fill: parent; margins: 18 }
            spacing: 6

            Text {
                text: card.icon
                font.pixelSize: 26
                color: "#7a6a5a"
            }

            Text {
                text: card.label
                font.family: "Noto Serif, Georgia, serif"
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: card.enabled ? "#3c3530" : "#a09590"
            }

            Text {
                Layout.fillWidth: true
                text: card.description
                font.pixelSize: 12
                color: "#9d9590"
                wrapMode: Text.WordWrap
            }
        }

        MouseArea {
            id: cardMa
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            enabled: card.enabled
            onClicked: card.tapped()
        }
    }
}
