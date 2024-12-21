package nex

import (
	"fmt"

	"github.com/RetendoNetwork/nex"
)

func SecureServer() {
	SecureServe := nex.NewServer()

	SecureServe.SetPRUDPVersion(0)
	SecureServe.SetKeySize(16)
	SecureServe.SetFragmentSize(900)
	SecureServe.SetAccessKey("ridfebb9")

	SecureServe.OnData("Data", func(packet *nex.PacketV0) {
		request := packet.RMCRequest()

		fmt.Printf("Protocol: %#v\n", request.GetProtocol())
		fmt.Printf("Method: %#v\n", request.GetMethod())
	})

	SecureServe.Listen(6001)
}
