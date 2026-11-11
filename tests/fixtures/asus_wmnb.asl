DefinitionBlock ("", "SSDT", 2, "P16TST", "WMNB", 0x00000001)
{
    Scope (\_SB)
    {
        Device (ATKD)
        {
            Name (_HID, "PNP0A06")
            Name (LAST, 0xAA)
            Method (WMNB, 3, Serialized)
            {
                If ((Arg1 == 0x53564544))
                {
                    CreateByteField (Arg2, 0x04, MODE)
                    LAST = MODE
                    Return (0x00000001)
                }
                If ((Arg1 == 0x53545344))
                {
                    Return (0x00010003)
                }
                Return (Zero)
            }
            Method (TEST, 0, Serialized)
            {
                Local0 = Buffer (0x14)
                {
                    0x75, 0x00, 0x12, 0x00, 0x01, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00
                }
                Return (WMNB (0, 0x53564544, Local0))
            }
            Method (TS2, 0, Serialized)
            {
                Local0 = Buffer (0x14)
                {
                    0x75, 0x00, 0x12, 0x00, 0x02, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                    0x00, 0x00, 0x00, 0x00
                }
                Return (WMNB (0, 0x53564544, Local0))
            }
        }
    }
}
