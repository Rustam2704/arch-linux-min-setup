# Builds the dock-rtl GTK module into the desktop tree (a 16 KB .so, committed).
OUT = ../../desktop/share/sky-desktop/libdock-rtl.so
$(OUT): dock-rtl.c
	gcc -shared -fPIC -O2 -Wall -o $(OUT) dock-rtl.c $$(pkg-config --cflags --libs gtk+-3.0)
	strip $(OUT)
