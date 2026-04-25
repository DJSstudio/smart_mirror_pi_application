// Login page — shown while waiting for a phone to scan the mirror QR code.
// Includes a collapsible Wi-Fi picker at the bottom so the operator can
// switch networks without leaving the page.
import QtQuick
import QtQuick.Layouts
import "../components"

Item {
    id: root

    // Warm off-white background
    Rectangle { anchors.fill: parent; color: "#F7F5F2" }

    // ── Main centred content ─────────────────────────────────────────────
    ColumnLayout {
        id: mainContent
        anchors {
            top: parent.top
            left: parent.left
            right: parent.right
            bottom: wifiPanel.top
        }
        spacing: 0

        Item { Layout.fillHeight: true }

        // Brand
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: "Smart Mirror"
            font.family: "Noto Serif, Georgia, serif"
            font.pixelSize: 36
            font.weight: Font.Medium
            color: "#1C1917"
        }

        Item { Layout.preferredHeight: 8 }

        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.fillWidth: true
            text: "Scan the QR code on the mirror with your phone\nto start or resume your session"
            font.pixelSize: 15
            color: "#6B6560"
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }

        Item { Layout.preferredHeight: 40 }

        // QR code card
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 240; height: 240
            radius: 20
            color: loginController.qrImageUrl.length > 0 ? "#FFFFFF" : "#F0EBE5"
            border.width: 1
            border.color: "#E8E2DC"

            Image {
                visible: loginController.qrImageUrl.length > 0
                anchors { fill: parent; margins: 14 }
                source: loginController.qrImageUrl
                fillMode: Image.PreserveAspectFit
                smooth: false
                cache: false
            }

            // Loading pulse
            Rectangle {
                visible: loginController.qrImageUrl.length === 0
                         && loginController.errorMessage.length === 0
                anchors.centerIn: parent
                width: 16; height: 16; radius: 8
                color: "#C4956A"

                SequentialAnimation on opacity {
                    running: parent.visible
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.2; duration: 600 }
                    NumberAnimation { to: 1.0; duration: 600 }
                }
            }
        }

        Item { Layout.preferredHeight: 32 }

        // Waiting indicator
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 10
            visible: loginController.isPending && loginController.errorMessage.length === 0

            Rectangle {
                width: 8; height: 8; radius: 4
                color: "#C4956A"

                SequentialAnimation on opacity {
                    running: loginController.isPending
                    loops: Animation.Infinite
                    NumberAnimation { to: 0.2; duration: 700 }
                    NumberAnimation { to: 1.0; duration: 700 }
                }
            }

            Text {
                text: "Waiting for device scan…"
                font.pixelSize: 14
                color: "#6B6560"
            }
        }

        // Error
        Rectangle {
            Layout.fillWidth: true
            Layout.leftMargin: 40; Layout.rightMargin: 40
            visible: loginController.errorMessage.length > 0
            height: 44; radius: 12
            color: "#8B2E2E"

            Text {
                anchors { fill: parent; leftMargin: 16; rightMargin: 16 }
                verticalAlignment: Text.AlignVCenter
                text: "  " + loginController.errorMessage
                font.pixelSize: 13
                color: "#FFFFFF"
                elide: Text.ElideRight
            }
        }

        Item { Layout.fillHeight: true }
    }

    // ── Wi-Fi panel (anchored to bottom, expands upward) ─────────────────
    Rectangle {
        id: wifiPanel
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: wifiExpanded ? expandedHeight : 56
        clip: true
        color: "#FFFFFF"
        border.width: 1
        border.color: "#E8E2DC"
        radius: 16

        // Square off the bottom corners so it flush-fits the window edge
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: parent.radius
            color: parent.color
        }

        Behavior on height { NumberAnimation { duration: 220; easing.type: Easing.OutQuad } }

        property bool wifiExpanded: false
        property int expandedHeight: 380

        readonly property bool wifiReady: typeof wifiController !== "undefined"
                                          && wifiController !== null
                                          && wifiController.available

        // ── Collapsed header row ─────────────────────────────────────────
        Item {
            id: wifiHeader
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 56

            RowLayout {
                anchors { fill: parent; leftMargin: 20; rightMargin: 16 }
                spacing: 10

                Text {
                    text: "Wi-Fi"
                    font.pixelSize: 14
                    font.weight: Font.Medium
                    color: "#C4956A"
                }

                Text {
                    Layout.fillWidth: true
                    text: {
                        if (!wifiPanel.wifiReady) return ""
                        var s = wifiController.status
                        if (s === "scanning")   return "Scanning…"
                        if (s === "connecting") return "Connecting…"
                        var ssid = wifiController.currentSsid
                        return ssid.length > 0 ? ssid : "Not connected"
                    }
                    font.pixelSize: 14
                    color: "#6B6560"
                    elide: Text.ElideRight
                }

                Rectangle {
                    width: 72; height: 32; radius: 8
                    color: headerMa.containsMouse ? "#F0EBE5" : "transparent"
                    visible: wifiPanel.wifiReady
                    Behavior on color { ColorAnimation { duration: 100 } }

                    Text {
                        anchors.centerIn: parent
                        text: wifiPanel.wifiExpanded ? "Close  ▲" : "Change  ▼"
                        font.pixelSize: 12
                        font.weight: Font.Medium
                        color: "#C4956A"
                    }

                    MouseArea {
                        id: headerMa
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            wifiPanel.wifiExpanded = !wifiPanel.wifiExpanded
                            if (wifiPanel.wifiExpanded && wifiController.networks.length === 0)
                                wifiController.scan()
                        }
                    }
                }
            }
        }

        // ── Expanded body ────────────────────────────────────────────────
        Item {
            id: expandedBody
            anchors {
                top: wifiHeader.bottom; bottom: parent.bottom
                left: parent.left; right: parent.right
                leftMargin: 16; rightMargin: 16; bottomMargin: 12
            }
            visible: wifiPanel.wifiExpanded && wifiPanel.wifiReady
            opacity: wifiPanel.wifiExpanded ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 150 } }

            property string selectedSsid: ""
            property bool selectedSecured: false

            ColumnLayout {
                anchors.fill: parent
                spacing: 8

                // Status / error banner
                Rectangle {
                    Layout.fillWidth: true
                    height: 36; radius: 8
                    visible: wifiController.status === "error"
                             || wifiController.status === "connected"
                    color: wifiController.status === "connected" ? "#1A3020" : "#3A2020"

                    Text {
                        anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                        verticalAlignment: Text.AlignVCenter
                        text: wifiController.status === "connected"
                              ? "Connected to " + wifiController.currentSsid
                              : wifiController.errorMessage
                        font.pixelSize: 13
                        color: wifiController.status === "connected" ? "#7DE870" : "#E87070"
                        elide: Text.ElideRight
                    }
                }

                // Network list box
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#F7F5F2"
                    radius: 10
                    border.width: 1
                    border.color: "#E8E2DC"
                    clip: true

                    // Empty / scanning placeholder
                    Text {
                        anchors.centerIn: parent
                        visible: wifiController.networks.length === 0
                        text: wifiController.status === "scanning"
                              ? "Scanning for networks…" : "No networks found"
                        font.pixelSize: 13
                        color: "#9E9890"
                    }

                    // Scrollable network list — Column (not ColumnLayout) inside Flickable
                    Flickable {
                        anchors { fill: parent; margins: 4 }
                        contentHeight: netCol.height
                        clip: true
                        visible: wifiController.networks.length > 0

                        Column {
                            id: netCol
                            width: parent.width
                            spacing: 0

                            Repeater {
                                model: wifiController.networks

                                Rectangle {
                                    width: netCol.width
                                    height: 44
                                    color: {
                                        if (modelData.inUse)
                                            return "#FFF8F0"
                                        if (modelData.ssid === expandedBody.selectedSsid)
                                            return "#F5EFE8"
                                        return netMa.containsMouse ? "#EEEAE5" : "transparent"
                                    }
                                    Behavior on color { ColorAnimation { duration: 80 } }

                                    // Divider
                                    Rectangle {
                                        anchors { bottom: parent.bottom; left: parent.left; right: parent.right; leftMargin: 8; rightMargin: 8 }
                                        height: 1
                                        color: "#E8E2DC"
                                        visible: index < wifiController.networks.length - 1
                                    }

                                    // Signal strength: 3 vertical bars using Item (not Row) to allow bottom-alignment
                                    Item {
                                        id: sigBars
                                        anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
                                        width: 18; height: 14

                                        Repeater {
                                            model: 3
                                            Rectangle {
                                                x: index * 6
                                                width: 4
                                                height: 4 + index * 5   // 4, 9, 14
                                                anchors.bottom: sigBars.bottom
                                                radius: 1
                                                color: {
                                                    var lit = modelData.signal > 66 ? 3
                                                            : modelData.signal > 33 ? 2 : 1
                                                    if (index < lit)
                                                        return modelData.signal > 66 ? "#4CAF50"
                                                             : modelData.signal > 33 ? "#FFC107"
                                                             : "#F44336"
                                                    return "#D4CFC9"
                                                }
                                            }
                                        }
                                    }

                                    // SSID text
                                    Text {
                                        anchors {
                                            left: sigBars.right; leftMargin: 8
                                            right: rowIcons.left; rightMargin: 6
                                            verticalCenter: parent.verticalCenter
                                        }
                                        text: modelData.ssid
                                        font.pixelSize: 14
                                        font.weight: modelData.inUse ? Font.DemiBold : Font.Normal
                                        color: "#1C1917"
                                        elide: Text.ElideRight
                                    }

                                    // Right-side icons: lock + checkmark
                                    Row {
                                        id: rowIcons
                                        anchors { right: parent.right; rightMargin: 12; verticalCenter: parent.verticalCenter }
                                        spacing: 6

                                        Text {
                                            visible: modelData.secured
                                            text: "lock"
                                            font.pixelSize: 11
                                            color: "#9E9890"
                                        }

                                        Text {
                                            visible: modelData.inUse
                                            text: "✓"
                                            font.pixelSize: 14
                                            font.weight: Font.Bold
                                            color: "#C4956A"
                                        }
                                    }

                                    MouseArea {
                                        id: netMa
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        enabled: wifiController.status !== "connecting"
                                        onClicked: {
                                            if (modelData.inUse) return
                                            expandedBody.selectedSsid = modelData.ssid
                                            expandedBody.selectedSecured = modelData.secured
                                            passwordField.text = ""
                                            if (modelData.secured)
                                                passwordField.forceActiveFocus()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // Password row — only shown when a network is selected
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    visible: expandedBody.selectedSsid.length > 0

                    Rectangle {
                        Layout.fillWidth: true
                        height: 40; radius: 8
                        color: "#F7F5F2"
                        border.width: 1
                        border.color: passwordField.activeFocus ? "#C4956A" : "#E8E2DC"
                        Behavior on border.color { ColorAnimation { duration: 100 } }

                        TextInput {
                            id: passwordField
                            anchors { fill: parent; leftMargin: 12; rightMargin: 12 }
                            verticalAlignment: TextInput.AlignVCenter
                            echoMode: TextInput.Password
                            font.pixelSize: 13
                            color: "#1C1917"
                            clip: true
                            onAccepted: doConnect()

                            // Placeholder
                            Text {
                                anchors.fill: parent
                                verticalAlignment: Text.AlignVCenter
                                text: expandedBody.selectedSecured
                                      ? "Password for " + expandedBody.selectedSsid
                                      : "Open network — tap Connect"
                                font.pixelSize: 13
                                color: "#B0A89E"
                                visible: passwordField.text.length === 0
                                         && !passwordField.activeFocus
                            }
                        }
                    }

                    Rectangle {
                        id: connectBtn
                        width: 96; height: 40; radius: 8
                        color: connectMa.containsMouse ? "#D4A57A" : "#C4956A"
                        Behavior on color { ColorAnimation { duration: 100 } }

                        Text {
                            anchors.centerIn: parent
                            text: wifiController.status === "connecting" ? "..." : "Connect"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: "#FFFFFF"
                        }

                        MouseArea {
                            id: connectMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: doConnect()
                        }
                    }
                }

                // Footer: refresh + skip login
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        height: 36; width: 110; radius: 8
                        color: scanMa.containsMouse ? "#F0EBE5" : "transparent"
                        border.width: 1; border.color: "#E8E2DC"
                        Behavior on color { ColorAnimation { duration: 100 } }

                        Text {
                            anchors.centerIn: parent
                            text: wifiController.status === "scanning" ? "Scanning..." : "Refresh"
                            font.pixelSize: 13
                            color: "#6B6560"
                        }

                        MouseArea {
                            id: scanMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            enabled: wifiController.status !== "scanning"
                                     && wifiController.status !== "connecting"
                            onClicked: wifiController.scan()
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: "Skip login"
                        font.pixelSize: 13
                        color: skipMa.containsMouse ? "#C4956A" : "#9E9890"
                        Behavior on color { ColorAnimation { duration: 100 } }

                        MouseArea {
                            id: skipMa
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: loginController.skipLogin()
                        }
                    }
                }
            }
        }

        // Regenerate QR after WiFi connect — new network means new IP
        Connections {
            target: wifiPanel.wifiReady ? wifiController : null
            function onChanged() {
                if (wifiController.status === "connected") {
                    wifiPanel.wifiExpanded = false
                    wifiRegenTimer.restart()
                }
            }
        }

        Timer {
            id: wifiRegenTimer
            interval: 1500
            repeat: false
            onTriggered: loginController.startLogin()
        }
    }

    // Helper called by both Connect button and Enter key
    function doConnect() {
        if (expandedBody.selectedSsid.length === 0) return
        if (wifiController.status === "connecting") return
        wifiController.connectToNetwork(expandedBody.selectedSsid, passwordField.text)
    }
}
