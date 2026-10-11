"""Native Kodular layout. Keep all interaction blocks in build_android.py."""


def decorate(children, page, component):
    def label(name, value, **props):
        return component(name, 'Label', 10, **dict(Text=value, Width=-2, FontSize=15,
                         TextColor='&HFF263D40') | props)

    def space(name, height=12):
        return label(name, '', Height=height, FontSize=1)

    def vertical(name, content, **props):
        item = component(name, 'VerticalArrangement', 10,
                         **dict(Width=-2, Height=-1, AlignHorizontal=3) | props)
        item['$Components'] = content
        return item

    def panel(name, content):
        return vertical(name, [space(name+'Top', 14),
                        vertical(name+'Content', content, Width=-1090),
                        space(name+'Bottom', 14)], BackgroundColor='&HFFFFFFFF')

    by = {c['$Name']: c for c in children}
    hidden = [c for c in children if c['$Type'] not in ('Label', 'Button', 'TextBox')]
    for c in children:
        if c['$Type'] == 'Label':
            c.update(FontSize='15', TextColor='&HFF263D40')
        elif c['$Type'] == 'Button':
            c.update(Height='56', FontSize='16')
        elif c['$Type'] == 'TextBox':
            c.update(Height='56', Multiline='False', BackgroundColor='&HFFF1F5F4',
                     TextColor='&HFF183B39', HintColor='&HFF697D7B',
                     LineColor='&HFFCBDAD6', HighlightColor='&HFF176C65')
    by['Heading'].update(Text='IDLAPS  /  TRIATHLON', FontSize='14',
                         FontBold='True', TextColor='&HFF176C65')
    if page == 1:
        by['Info'].update(Text='Hubungkan sekali.\nFokus pada lintasan.', FontSize='25', FontBold='True')
        by['Status'].update(Text='Menyiapkan penyimpanan…', FontSize='13')
        by['Continue'].update(Text='Lanjutkan pencatatan', BackgroundColor='&HFFE0EEEA', TextColor='&HFF17564F')
        layout = [space('Top', 24), by['Heading'], space('BrandGap', 16), by['Info'], space('IntroGap', 20),
                  panel('PairPanel', [label('PairTitle', 'PASANGKAN PONSEL', FontSize=12, FontBold='True'),
                        space('PairGap'), label('CodeLabel', 'Kode pemasangan dari admin', FontSize=13), by['Code'],
                        space('CodeGap'), by['Pair']]),
                  space('StatusGap', 16), by['Status'], space('ContinueGap'), by['Continue'],
                  space('FootGap', 20), label('Footnote', 'Sudah dipasangkan? Pencatatan tetap bisa dibuka tanpa internet.',
                                            FontSize=13, TextColor='&HFF657A77'), space('Bottom', 24)]
    else:
        by['Assignment'].update(FontSize='21', FontBold='True')
        by['ClockStatus'].update(FontSize='13', TextColor='&HFF876022')
        by['Bib'].update(FontSize='38', FontBold='True', TextAlignment='1', Height='80', Hint='BIB · 1–3 digit', InputType='5')
        by['Lap'].update(InputType='5', Height='48')
        by['Lap'].pop('NumbersOnly', None)
        by['Save'].update(Height='64', FontSize='18')
        by['Run'].update(Height='64', FontSize='18', BackgroundColor='&HFF28527B')
        by['SyncStatus'].update(FontSize='14', TextColor='&HFF176C65')
        by['Review'].update(BackgroundColor='&HFFF8EDEA', TextColor='&HFF9A4436', FontSize='14', Height='48')
        by['Switch'].update(BackgroundColor='&HFFE0EEEA', TextColor='&HFF17564F', FontSize='14', Height='48')
        by['Refresh'].update(Text='Periksa jam & konfigurasi', BackgroundColor='&HFFE0EEEA',
                             TextColor='&HFF17564F', FontSize='14', Height='48')
        by['History'].update(FontSize='14')
        layout = [space('Top', 18), by['Heading'], space('BrandGap'), by['Assignment'], by['ClockStatus'],
                  space('CaptureGap', 16), panel('CapturePanel', [
                      label('BibLabel', 'NOMOR PESERTA', FontSize=12, FontBold='True'), by['Bib'], by['Participant'],
                      label('LapLabel', 'Putaran yang sedang dicatat', FontSize=13), by['Lap'],
                      space('SaveGap', 8), by['Save'], by['Run']]),
                  space('SyncGap', 14), panel('SyncPanel', [by['SyncStatus'], space('SendGap', 8), by['Send']]),
                  space('HistoryGap', 18), label('HistoryTitle', 'CATATAN TERBARU', FontSize=12, FontBold='True'),
                  by['History'], space('ReviewGap'), by['Review'], by['Refresh'], by['Switch'], space('Bottom', 24)]
    return [vertical('Page', layout, Width=-1092)] + hidden
