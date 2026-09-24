/* dock-rtl - a GTK 3 module that turns the dock (xfce4-docklike-plugin) right-to-left.
 *
 * docklike appends every new window group at the end of its box; in a right-to-left
 * box the "end" is the left side, so pinned apps stay at the right (kitty last in
 * the pinned list = rightmost) and new programs open at the left edge, the way the
 * user wants it. Loaded into every GTK program through GTK_MODULES (set in the
 * session script), it does nothing unless the process is the panel wrapper hosting
 * libdocklike.so - it looks at its own command line, not at GTK's argv.
 *
 * Build: make (see Makefile); the .so lives in desktop/share/sky-desktop/.
 */
#include <gtk/gtk.h>
#include <stdio.h>
#include <string.h>

G_MODULE_EXPORT void
gtk_module_init (gint *argc, gchar ***argv)
{
  char buf[4096];
  FILE *f = fopen ("/proc/self/cmdline", "rb");
  if (!f)
    return;
  size_t n = fread (buf, 1, sizeof buf - 1, f);
  fclose (f);
  for (size_t i = 0; i < n; i++)           /* NUL-separated arguments */
    if (buf[i] == '\0')
      buf[i] = ' ';
  buf[n] = '\0';
  if (strstr (buf, "libdocklike"))
    gtk_widget_set_default_direction (GTK_TEXT_DIR_RTL);
}
