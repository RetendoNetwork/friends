package main

import (
	"sync"

	"github.com/RetendoNetwork/friends/nex"
)

var wg sync.WaitGroup

func main() {
	wg.Add(3)

	go nex.AuthenticationServer()

	wg.Wait()
}
