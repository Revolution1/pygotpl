package main

import (
	"encoding/hex"
	"encoding/json"
	"os"
	"time"
)

type instant struct {
	Unix       int64  `json:"unix"`
	Nanosecond int    `json:"nanosecond"`
	Location   string `json:"location"`
}

func value(t time.Time) instant {
	return instant{t.Unix(), t.Nanosecond(), t.Location().String()}
}

type vector struct {
	Name        string  `json:"name"`
	Value       instant `json:"value"`
	ISOYear     int     `json:"iso_year"`
	ISOWeek     int     `json:"iso_week"`
	Zone        string  `json:"zone"`
	Offset      int     `json:"offset"`
	ZoneStart   instant `json:"zone_start"`
	ZoneEnd     instant `json:"zone_end"`
	BinaryHex   string  `json:"binary_hex"`
	Text        string  `json:"text"`
	JSON        string  `json:"json"`
	TextDecoded instant `json:"text_decoded"`
	String      string  `json:"string"`
	GoString    string  `json:"go_string"`
}

func makeVector(name string, t time.Time) vector {
	year, week := t.ISOWeek()
	zone, offset := t.Zone()
	start, end := t.ZoneBounds()
	binary, err := t.MarshalBinary()
	if err != nil {
		panic(err)
	}
	text, err := t.MarshalText()
	if err != nil {
		panic(err)
	}
	jsonBytes, err := t.MarshalJSON()
	if err != nil {
		panic(err)
	}
	parsed, err := time.Parse(time.RFC3339Nano, string(text))
	if err != nil {
		panic(err)
	}
	return vector{
		name, value(t), year, week, zone, offset, value(start), value(end),
		hex.EncodeToString(binary), string(text), string(jsonBytes), value(parsed),
		t.String(), t.GoString(),
	}
}

func main() {
	newYork, err := time.LoadLocation("America/New_York")
	if err != nil {
		panic(err)
	}
	fixedSeconds := time.FixedZone("LMT", 5*60+21)
	vectors := []vector{
		makeVector("utc-year-boundary", time.Date(2021, 1, 1, 0, 0, 0, 123456789, time.UTC)),
		makeVector("new-york-winter", time.Date(2024, 1, 15, 12, 0, 0, 987654321, newYork)),
		makeVector("new-york-summer", time.Date(2024, 7, 15, 12, 0, 0, 0, newYork)),
		makeVector("fixed-second-offset", time.Date(1880, 1, 2, 3, 4, 5, 6, fixedSeconds)),
		makeVector("new-york-future", time.Date(2040, 7, 15, 12, 0, 0, 0, newYork)),
	}
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(struct {
		Schema  int      `json:"schema"`
		Vectors []vector `json:"vectors"`
	}{1, vectors}); err != nil {
		panic(err)
	}
}
