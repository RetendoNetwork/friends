package nex

import (
	"fmt"

	"github.com/RetendoNetwork/nex"
)

func AuthenticationServer() {
	AuthServe := nex.NewServer()

	AuthServe.SetPRUDPVersion(0)
	AuthServe.SetKeySize(16)
	AuthServe.SetAccessKey("ridfebb9")

	AuthServe.OnData("Data", func(packet *nex.PacketV0) {
		request := packet.RMCRequest()

		fmt.Printf("Protocol: %#v\n", request.GetProtocol())
		fmt.Printf("Method: %#v\n", request.GetMethod())
	})

	AuthServe.Listen(6000)
}
