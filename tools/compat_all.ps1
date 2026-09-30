# Full server compatibility run (see the README). Sequential: all servers share one port.
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$py = "tools\.venv\Scripts\python"
$f = "$root/build/testmods/fabric"
$n = "$root/build/testmods/neoforge"
$bof = (Get-ChildItem "$root/fabric/build/libs/big_oceans-*[0-9].jar").FullName
$bon = (Get-ChildItem "$root/neoforge/build/libs/big_oceans-*[0-9].jar").FullName
$at = "5:-7680:-1024"

& $py tools\compat.py fabric build/compat/fabric.json $at `
    "big_oceans=$bof" "big_oceans_repeat=$bof" "vanilla=-" "lithium=$bof,$f/lithium.jar" "c2me=$bof,$f/c2me.jar" `
    "ferritecore_modernfix=$bof,$f/ferritecore.jar,$f/modernfix.jar" "dh=$bof,$f/dh.jar" "dh_without_big_oceans=$f/dh.jar" `
    "terralith_only=$f/terralith.jar,$f/lithostitched.jar" "terralith=$bof,$f/terralith.jar,$f/lithostitched.jar" `
    "tectonic_only=$f/tectonic.jar,$f/lithostitched.jar" "tectonic=$bof,$f/tectonic.jar,$f/lithostitched.jar"
& $py tools\compat.py quilt build/compat/quilt.json $at "big_oceans=$bof" "vanilla=-"
& $py tools\compat.py neoforge build/compat/neoforge2.json $at `
    "big_oceans=$bon" "big_oceans_repeat=$bon" "dh_without_big_oceans=$n/dh.jar" `
    "terralith_only=$n/terralith.jar,$n/lithostitched.jar" "terralith=$bon,$n/terralith.jar,$n/lithostitched.jar"
& $py tools\structures.py fabric build/compat/structures.json 5 6 7
"ALL_DONE"
