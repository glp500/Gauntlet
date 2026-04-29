using System.Data;
using System.Diagnostics;
using System.Drawing.Drawing2D;
using System.Globalization;
using System.Linq;
using System.Text;

namespace GauntletLayoutExe;

public sealed class LayoutForm : Form
{
    private readonly FileListBox _fileListBox;
    private readonly DarkVScrollBar _fileScrollBar;
    private readonly DarkVScrollBar _dataGridVScrollBar;
    private readonly DarkHScrollBar _dataGridHScrollBar;
    private readonly HashSet<string> _expandedExplorerDirectories = new(StringComparer.OrdinalIgnoreCase);
    private readonly SplitContainer _rootSplit;
    private readonly SplitContainer _leftMiddleSplit;
    private readonly SplitContainer _leftTopBottomSplit;
    private readonly SplitContainer _middleTopBottomSplit;
    private readonly SplitContainer _rightTopBottomSplit;
    private readonly SplitContainer _rightLowerSplit;
    private TextBox _instructionsInput = null!;
    private DataGridView _dataGridView = null!;
    private Panel _graphHostPanel = null!;
    private Label _graphStatusLabel = null!;
    private ComboBox _xVariableInput = null!;
    private ComboBox _yVariableInput = null!;
    private DataTable? _activeDataTable;
    private string? _activeDatasetPath;
    private string? _explorerRootPath;
    private int _hoveredExplorerIndex = -1;
    private bool _layoutInitialized;

    public LayoutForm()
    {
        AutoScaleMode = AutoScaleMode.None;
        BackColor = Color.FromArgb(30, 30, 30);
        Font = new Font("Segoe UI", 9F, FontStyle.Regular, GraphicsUnit.Point);
        DoubleBuffered = true;
        FormBorderStyle = FormBorderStyle.Sizable;
        KeyPreview = true;
        MinimumSize = new Size(1280, 720);
        StartPosition = FormStartPosition.CenterScreen;
        Bounds = new Rectangle(0, 0, 1440, 900);
        Text = "Gauntlet IDE (Prototype)";

        _rootSplit = new SplitContainer
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(37, 37, 38),
            BorderStyle = BorderStyle.None,
            Orientation = Orientation.Vertical,
            SplitterWidth = 5
        };

        _leftMiddleSplit = new SplitContainer
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(37, 37, 38),
            BorderStyle = BorderStyle.None,
            Orientation = Orientation.Vertical,
            SplitterWidth = 5
        };

        _leftTopBottomSplit = new SplitContainer
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(37, 37, 38),
            BorderStyle = BorderStyle.None,
            Orientation = Orientation.Horizontal,
            SplitterWidth = 5
        };

        _middleTopBottomSplit = new SplitContainer
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(37, 37, 38),
            BorderStyle = BorderStyle.None,
            Orientation = Orientation.Horizontal,
            SplitterWidth = 5
        };

        _rightTopBottomSplit = new SplitContainer
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(37, 37, 38),
            BorderStyle = BorderStyle.None,
            Orientation = Orientation.Horizontal,
            SplitterWidth = 5
        };

        _rightLowerSplit = new SplitContainer
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(37, 37, 38),
            BorderStyle = BorderStyle.None,
            Orientation = Orientation.Horizontal,
            SplitterWidth = 5
        };

        _fileListBox = BuildFileExplorer();
        _fileScrollBar = new DarkVScrollBar
        {
            Dock = DockStyle.Right,
            Width = 14
        };
        _fileScrollBar.ValueChanged += value =>
        {
            if (_fileListBox.Items.Count == 0)
            {
                return;
            }

            var maxTop = Math.Max(0, _fileListBox.Items.Count - Math.Max(1, _fileListBox.ClientSize.Height / _fileListBox.ItemHeight));
            _fileListBox.TopIndex = Math.Max(0, Math.Min(value, maxTop));
        };
        _fileListBox.SelectedIndexChanged += (_, _) => SyncFileScrollBar();
        _fileListBox.MouseWheel += (_, _) => SyncFileScrollBar();
        _fileListBox.Resize += (_, _) => SyncFileScrollBar();
        _fileListBox.MouseMove += HandleFileExplorerMouseMove;
        _fileListBox.MouseLeave += HandleFileExplorerMouseLeave;
        _fileListBox.MouseDoubleClick += HandleFileExplorerDoubleClick;
        _dataGridVScrollBar = new DarkVScrollBar
        {
            Dock = DockStyle.Right,
            Width = 14,
            Visible = false
        };
        _dataGridVScrollBar.ValueChanged += HandleDataGridVerticalScroll;
        _dataGridHScrollBar = new DarkHScrollBar
        {
            Dock = DockStyle.Bottom,
            Height = 14,
            Visible = false
        };
        _dataGridHScrollBar.ValueChanged += HandleDataGridHorizontalScroll;

        _leftTopBottomSplit.Panel1.Controls.Add(BuildFileInputPanel());
        _leftTopBottomSplit.Panel2.Controls.Add(BuildInstructionsPanel());

        _middleTopBottomSplit.Panel1.Controls.Add(BuildDataViewerPanel());
        _middleTopBottomSplit.Panel2.Controls.Add(BuildSection("Overview", BuildEmptyPanel()));

        _rightTopBottomSplit.Panel1.Controls.Add(BuildSection("Graph Viewer/Editor", BuildGraphPanel()));
        _rightTopBottomSplit.Panel2.Controls.Add(_rightLowerSplit);
        _rightLowerSplit.Panel1.Controls.Add(BuildVariableEditorPanel());
        _rightLowerSplit.Panel2.Controls.Add(BuildSection("Terminal", BuildEmptyPanel()));

        _leftMiddleSplit.Panel1.Controls.Add(_leftTopBottomSplit);
        _leftMiddleSplit.Panel2.Controls.Add(_middleTopBottomSplit);

        _rootSplit.Panel1.Controls.Add(_leftMiddleSplit);
        _rootSplit.Panel2.Controls.Add(_rightTopBottomSplit);
        Controls.Add(_rootSplit);

        Load += HandleLoad;
        Shown += (_, _) => ApplyInitialLayout();
        Resize += (_, _) => ApplyInitialLayout();
        KeyDown += HandleKeyDown;
        PopulateFileExplorer();
    }

    private void HandleLoad(object? sender, EventArgs e)
    {
        CenterToScreen();
        ApplyInitialLayout();
    }

    private void HandleKeyDown(object? sender, KeyEventArgs e)
    {
        if (e.KeyCode == Keys.Escape)
        {
            Close();
        }
    }

    private void ApplyInitialLayout()
    {
        if (_layoutInitialized || ClientSize.Width <= 0 || ClientSize.Height <= 0)
        {
            return;
        }

        // Ratios tuned to match Assets/UI_V0.png starting geometry.
        var totalWidth = _rootSplit.ClientSize.Width;
        _rootSplit.SplitterDistance = (int)Math.Round(totalWidth * 0.512); // left+middle / right

        var leftMiddleWidth = _leftMiddleSplit.ClientSize.Width;
        _leftMiddleSplit.SplitterDistance = (int)Math.Round(leftMiddleWidth * 0.406); // left / middle

        _leftTopBottomSplit.SplitterDistance = (int)Math.Round(_leftTopBottomSplit.ClientSize.Height * 0.556);
        _middleTopBottomSplit.SplitterDistance = (int)Math.Round(_middleTopBottomSplit.ClientSize.Height * 0.644);
        _rightTopBottomSplit.SplitterDistance = (int)Math.Round(_rightTopBottomSplit.ClientSize.Height * 0.68);
        _rightLowerSplit.SplitterDistance = (int)Math.Round(_rightLowerSplit.ClientSize.Height * 0.44);

        _layoutInitialized = true;
    }

    private Control BuildFileInputPanel()
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(30, 30, 30),
            Padding = new Padding(8)
        };

        panel.Controls.Add(_fileListBox);
        panel.Controls.Add(_fileScrollBar);
        return BuildSection("File Input", panel);
    }

    private Control BuildInstructionsPanel()
    {
        _instructionsInput = new TextBox
        {
            Dock = DockStyle.Fill,
            Multiline = true,
            AcceptsTab = true,
            ScrollBars = ScrollBars.None,
            BackColor = Color.FromArgb(30, 30, 30),
            ForeColor = Color.Gainsboro,
            BorderStyle = BorderStyle.FixedSingle,
            Text = string.Empty
        };

        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(30, 30, 30),
            Padding = new Padding(8)
        };
        panel.Controls.Add(_instructionsInput);
        return BuildSection("Instructions", panel);
    }

    private Control BuildDataViewerPanel()
    {
        _dataGridView = new DataGridView
        {
            Dock = DockStyle.Fill,
            ReadOnly = true,
            AllowUserToAddRows = false,
            AllowUserToDeleteRows = false,
            AllowUserToResizeRows = false,
            SelectionMode = DataGridViewSelectionMode.FullRowSelect,
            BackgroundColor = Color.FromArgb(30, 30, 30),
            BorderStyle = BorderStyle.None,
            ScrollBars = ScrollBars.None,
            RowHeadersVisible = false,
            EnableHeadersVisualStyles = false,
            ColumnHeadersDefaultCellStyle = new DataGridViewCellStyle
            {
                BackColor = Color.FromArgb(45, 45, 45),
                ForeColor = Color.Gainsboro
            },
            DefaultCellStyle = new DataGridViewCellStyle
            {
                BackColor = Color.FromArgb(30, 30, 30),
                ForeColor = Color.Gainsboro,
                SelectionBackColor = Color.FromArgb(9, 71, 113),
                SelectionForeColor = Color.White
            }
        };
        _dataGridView.Scroll += (_, _) => SyncDataViewerScrollBars();
        _dataGridView.Resize += (_, _) => SyncDataViewerScrollBars();
        _dataGridView.DataBindingComplete += (_, _) => SyncDataViewerScrollBars();
        _dataGridView.ColumnWidthChanged += (_, _) => SyncDataViewerScrollBars();
        _dataGridView.RowsAdded += (_, _) => SyncDataViewerScrollBars();
        _dataGridView.RowsRemoved += (_, _) => SyncDataViewerScrollBars();

        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(30, 30, 30),
            Padding = new Padding(0)
        };
        panel.Controls.Add(_dataGridView);
        panel.Controls.Add(_dataGridVScrollBar);
        panel.Controls.Add(_dataGridHScrollBar);

        return BuildSection("Data Viewer", panel);
    }

    private Control BuildGraphPanel()
    {
        _graphHostPanel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(30, 30, 30)
        };

        _graphStatusLabel = new Label
        {
            Dock = DockStyle.Fill,
            ForeColor = Color.Gainsboro,
            Text = "Waiting...",
            TextAlign = ContentAlignment.MiddleCenter
        };
        _graphHostPanel.Controls.Add(_graphStatusLabel);
        return _graphHostPanel;
    }

    private Control BuildVariableEditorPanel()
    {
        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(30, 30, 30),
            ColumnCount = 2,
            RowCount = 5,
            Padding = new Padding(8, 0, 8, 0),
            Margin = new Padding(0)
        };

        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 80f));
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 50f));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 26f));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 26f));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 34f));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 50f));

        _xVariableInput = new ComboBox
        {
            Dock = DockStyle.Fill,
            DropDownStyle = ComboBoxStyle.DropDownList,
            Margin = new Padding(0, 2, 0, 2),
            BackColor = Color.FromArgb(45, 45, 45),
            ForeColor = Color.Gainsboro,
            FlatStyle = FlatStyle.Flat
        };
        _yVariableInput = new ComboBox
        {
            Dock = DockStyle.Fill,
            DropDownStyle = ComboBoxStyle.DropDownList,
            Margin = new Padding(0, 2, 0, 2),
            BackColor = Color.FromArgb(45, 45, 45),
            ForeColor = Color.Gainsboro,
            FlatStyle = FlatStyle.Flat
        };
        var apply = BuildActionButton("Apply Labels");
        apply.Width = 140;
        apply.Height = 28;
        apply.Dock = DockStyle.None;
        apply.Anchor = AnchorStyles.Left;
        apply.Margin = new Padding(0);
        apply.Text = "Apply Variables";
        apply.Click += (_, _) => ApplyVariables();

        layout.Controls.Add(new Label { Text = "X Var", ForeColor = Color.Gainsboro, Dock = DockStyle.Fill, Margin = new Padding(0), TextAlign = ContentAlignment.MiddleLeft }, 0, 1);
        layout.Controls.Add(_xVariableInput, 1, 1);
        layout.Controls.Add(new Label { Text = "Y Var", ForeColor = Color.Gainsboro, Dock = DockStyle.Fill, Margin = new Padding(0), TextAlign = ContentAlignment.MiddleLeft }, 0, 2);
        layout.Controls.Add(_yVariableInput, 1, 2);
        layout.Controls.Add(apply, 1, 3);

        return BuildSection("Variable Editor", layout);
    }

    private static Panel BuildEmptyPanel()
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(37, 37, 38),
            Margin = new Padding(4)
        };
        return panel;
    }

    private static Panel BuildSection(string title, Control body)
    {
        var outer = new Panel
        {
            Dock = DockStyle.Fill,
            Padding = new Padding(0),
            BackColor = Color.FromArgb(37, 37, 38),
            Margin = new Padding(0)
        };

        var header = new Label
        {
            Dock = DockStyle.Top,
            Height = 30,
            Text = $"  {title}",
            ForeColor = Color.Gainsboro,
            BackColor = Color.FromArgb(45, 45, 45),
            TextAlign = ContentAlignment.MiddleLeft,
            Font = new Font("Segoe UI", 11F, FontStyle.Regular, GraphicsUnit.Point)
        };

        body.Dock = DockStyle.Fill;
        outer.Controls.Add(body);
        outer.Controls.Add(header);
        return outer;
    }

    private FileListBox BuildFileExplorer()
    {
        var listBox = new FileListBox
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(30, 30, 30),
            ForeColor = Color.Gainsboro,
            BorderStyle = BorderStyle.None,
            DrawMode = DrawMode.OwnerDrawFixed,
            ItemHeight = 26,
            IntegralHeight = false,
            ScrollAlwaysVisible = false
        };
        listBox.DrawItem += (_, e) =>
        {
            if (e.Index < 0 || e.Index >= listBox.Items.Count)
            {
                return;
            }

            var item = listBox.Items[e.Index] as ExplorerItem;
            var bounds = e.Bounds;
            var isHovered = e.Index == _hoveredExplorerIndex;
            var isActive = e.Index == listBox.SelectedIndex;
            using var backgroundBrush = new SolidBrush(listBox.BackColor);
            e.Graphics.FillRectangle(backgroundBrush, bounds);

            if (item is null)
            {
                return;
            }

            if (isHovered || isActive)
            {
                var highlightBounds = new Rectangle(bounds.X + 2, bounds.Y + 2, Math.Max(0, bounds.Width - 4), Math.Max(0, bounds.Height - 4));
                if (highlightBounds.Width > 0 && highlightBounds.Height > 0)
                {
                    using var highlightBrush = new SolidBrush(Color.FromArgb(13, 255, 255, 255));
                    using var highlightPath = CreateExplorerRoundedRectPath(highlightBounds, 6);
                    e.Graphics.FillPath(highlightBrush, highlightPath);
                }
            }

            var glyphX = 8 + (item.Depth * 16);
            var textX = glyphX;
            var textColor = item.IsPlaceholder
                ? Color.FromArgb(140, 140, 140)
                : item.FullPath.Equals(_activeDatasetPath, StringComparison.OrdinalIgnoreCase)
                    ? Color.FromArgb(106, 215, 141)
                    : item.IsRoot
                        ? Color.FromArgb(220, 220, 220)
                        : Color.Gainsboro;

            if (item.IsDirectory)
            {
                var chevron = _expandedExplorerDirectories.Contains(item.FullPath) ? "▾" : "▸";
                TextRenderer.DrawText(
                    e.Graphics,
                    chevron,
                    e.Font ?? Font,
                    new Rectangle(glyphX, bounds.Top + 1, 14, bounds.Height - 2),
                    textColor,
                    TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
                textX += 14;
            }
            else
            {
                DrawFileGlyph(e.Graphics, glyphX + 2, bounds.Top + 7, Color.FromArgb(196, 138, 255));
                textX += 18;
            }

            using var itemFont = item.IsRoot
                ? new Font(e.Font ?? Font, FontStyle.Bold)
                : null;
            TextRenderer.DrawText(
                e.Graphics,
                item.DisplayName,
                itemFont ?? (e.Font ?? Font),
                new Rectangle(textX, bounds.Top + 1, Math.Max(0, bounds.Width - textX - 6), bounds.Height - 2),
                textColor,
                TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPadding);
        };
        return listBox;
    }

    private static Button BuildActionButton(string text)
    {
        var button = new Button
        {
            Text = text,
            Width = 160,
            Height = 28,
            BackColor = Color.FromArgb(7, 55, 99),
            ForeColor = Color.White,
            FlatStyle = FlatStyle.Flat,
            Margin = new Padding(0),
            Dock = DockStyle.Fill,
            AutoEllipsis = false,
            UseCompatibleTextRendering = true
        };
        button.FlatAppearance.BorderColor = Color.FromArgb(14, 74, 126);
        button.FlatAppearance.BorderSize = 1;
        button.FlatAppearance.MouseOverBackColor = Color.FromArgb(10, 66, 116);
        button.FlatAppearance.MouseDownBackColor = Color.FromArgb(5, 43, 78);
        return button;
    }

    private void PopulateFileExplorer()
    {
        var selectedPath = (_fileListBox.SelectedItem as ExplorerItem)?.FullPath ?? _activeDatasetPath;
        _fileListBox.BeginUpdate();
        try
        {
            _fileListBox.Items.Clear();
            _explorerRootPath = ResolveExplorerRootPath();
            if (_explorerRootPath is null)
            {
                _fileListBox.Items.Add(ExplorerItem.Placeholder("le_input_folder not found"));
                return;
            }

            if (_expandedExplorerDirectories.Count == 0)
            {
                _expandedExplorerDirectories.Add(_explorerRootPath);
            }

            AddExplorerDirectory(_explorerRootPath, depth: 0, isRoot: true);
            RestoreExplorerSelection(selectedPath);
        }
        finally
        {
            _fileListBox.EndUpdate();
            SyncFileScrollBar();
        }
    }

    private void SyncFileScrollBar()
    {
        var visibleItems = Math.Max(1, _fileListBox.ClientSize.Height / _fileListBox.ItemHeight);
        var maxTop = Math.Max(0, _fileListBox.Items.Count - visibleItems);
        _fileScrollBar.Maximum = maxTop;
        _fileScrollBar.Value = Math.Max(0, Math.Min(_fileListBox.TopIndex, maxTop));
        _fileScrollBar.Visible = maxTop > 0;
    }

    private void HandleDataGridVerticalScroll(int value)
    {
        if (_dataGridView.RowCount == 0)
        {
            return;
        }

        var targetIndex = Math.Max(0, Math.Min(value, Math.Max(0, _dataGridView.RowCount - 1)));
        try
        {
            _dataGridView.FirstDisplayedScrollingRowIndex = targetIndex;
        }
        catch
        {
            // Ignore transient invalid indices while the grid is rebinding/resizing.
        }
    }

    private void HandleDataGridHorizontalScroll(int value)
    {
        _dataGridView.HorizontalScrollingOffset = Math.Max(0, value);
    }

    private void SyncDataViewerScrollBars()
    {
        if (_dataGridView.DataSource is null && _dataGridView.RowCount == 0 && _dataGridView.ColumnCount == 0)
        {
            _dataGridVScrollBar.Visible = false;
            _dataGridHScrollBar.Visible = false;
            return;
        }

        var displayedRows = Math.Max(1, _dataGridView.DisplayedRowCount(false));
        var maxFirstRow = Math.Max(0, _dataGridView.RowCount - displayedRows);
        _dataGridVScrollBar.Maximum = maxFirstRow;
        _dataGridVScrollBar.Value = Math.Max(0, Math.Min(_dataGridView.FirstDisplayedScrollingRowIndex, maxFirstRow));
        _dataGridVScrollBar.Visible = maxFirstRow > 0;

        var visibleColumns = _dataGridView.Columns.Cast<DataGridViewColumn>().Where(column => column.Visible).ToList();
        var totalColumnWidth = visibleColumns.Sum(column => column.Width);
        var rowHeaderWidth = _dataGridView.RowHeadersVisible ? _dataGridView.RowHeadersWidth : 0;
        var availableWidth = Math.Max(0, _dataGridView.ClientSize.Width - rowHeaderWidth);
        var maxHorizontalOffset = Math.Max(0, totalColumnWidth - availableWidth);
        _dataGridHScrollBar.Maximum = maxHorizontalOffset;
        _dataGridHScrollBar.Value = Math.Max(0, Math.Min(_dataGridView.HorizontalScrollingOffset, maxHorizontalOffset));
        _dataGridHScrollBar.Visible = maxHorizontalOffset > 0;
    }

    private void HandleFileExplorerMouseMove(object? sender, MouseEventArgs e)
    {
        var hoveredIndex = _fileListBox.IndexFromPoint(e.Location);
        if (hoveredIndex == ListBox.NoMatches)
        {
            hoveredIndex = -1;
        }

        if (_hoveredExplorerIndex == hoveredIndex)
        {
            return;
        }

        _hoveredExplorerIndex = hoveredIndex;
        _fileListBox.Invalidate();
    }

    private void HandleFileExplorerMouseLeave(object? sender, EventArgs e)
    {
        if (_hoveredExplorerIndex < 0)
        {
            return;
        }

        _hoveredExplorerIndex = -1;
        _fileListBox.Invalidate();
    }

    private void HandleFileExplorerDoubleClick(object? sender, MouseEventArgs e)
    {
        var index = _fileListBox.IndexFromPoint(e.Location);
        if (index < 0 || index >= _fileListBox.Items.Count)
        {
            return;
        }

        _fileListBox.SelectedIndex = index;
        if (_fileListBox.Items[index] is not ExplorerItem item || item.IsPlaceholder)
        {
            return;
        }

        if (item.IsDirectory)
        {
            ToggleExplorerDirectory(item.FullPath);
            return;
        }

        LoadDatasetFromPath(item.FullPath);
    }

    private void LoadDatasetFromPath(string datasetPath)
    {
        if (!datasetPath.EndsWith(".csv", StringComparison.OrdinalIgnoreCase))
        {
            _graphStatusLabel.Text = $"Unsupported dataset: {Path.GetFileName(datasetPath)}";
            return;
        }

        try
        {
            _activeDataTable = LoadCsvTable(datasetPath);
            _activeDatasetPath = datasetPath;
            _dataGridView.DataSource = _activeDataTable;
            PopulateVariableSelectors(_activeDataTable);
            var (defaultX, defaultY) = GetDefaultAxisColumns(_activeDataTable);
            SelectVariable(_xVariableInput, defaultX);
            SelectVariable(_yVariableInput, defaultY);
            _graphStatusLabel.Text = $"Loaded {Path.GetFileName(datasetPath)}. Generating graphs...";
            PopulateFileExplorer();
            RenderGraphsWithPython();
        }
        catch (Exception ex)
        {
            _graphStatusLabel.Text = $"Dataset load failed: {ex.Message}";
        }
    }

    private void ApplyVariables()
    {
        if (_activeDataTable is null || _activeDatasetPath is null)
        {
            return;
        }

        RenderGraphsWithPython();
    }

    private static (string XAxis, string YAxis) GetDefaultAxisColumns(DataTable table)
    {
        var numericColumns = table.Columns
            .Cast<DataColumn>()
            .Where(column => ColumnIsMostlyNumeric(table, column))
            .Select(column => column.ColumnName)
            .ToList();

        if (numericColumns.Count >= 2)
        {
            return (numericColumns[0], numericColumns[1]);
        }

        if (numericColumns.Count == 1)
        {
            return (numericColumns[0], numericColumns[0]);
        }

        var allColumns = table.Columns.Cast<DataColumn>().Select(column => column.ColumnName).ToList();
        if (allColumns.Count >= 2)
        {
            return (allColumns[0], allColumns[1]);
        }

        if (allColumns.Count == 1)
        {
            return (allColumns[0], allColumns[0]);
        }

        return (string.Empty, string.Empty);
    }

    private static bool ColumnIsMostlyNumeric(DataTable table, DataColumn column)
    {
        if (table.Rows.Count == 0)
        {
            return false;
        }

        var populatedCount = 0;
        var numericCount = 0;
        foreach (DataRow row in table.Rows)
        {
            var raw = row[column]?.ToString();
            if (string.IsNullOrWhiteSpace(raw))
            {
                continue;
            }

            populatedCount++;
            if (double.TryParse(raw, NumberStyles.Any, CultureInfo.InvariantCulture, out _) ||
                double.TryParse(raw, NumberStyles.Any, CultureInfo.CurrentCulture, out _))
            {
                numericCount++;
            }
        }

        return populatedCount > 0 && (double)numericCount / populatedCount >= 0.6;
    }

    private void PopulateVariableSelectors(DataTable table)
    {
        var columns = table.Columns.Cast<DataColumn>().Select(column => column.ColumnName).ToArray();

        _xVariableInput.BeginUpdate();
        _yVariableInput.BeginUpdate();
        try
        {
            _xVariableInput.Items.Clear();
            _yVariableInput.Items.Clear();
            _xVariableInput.Items.AddRange(columns);
            _yVariableInput.Items.AddRange(columns);
        }
        finally
        {
            _xVariableInput.EndUpdate();
            _yVariableInput.EndUpdate();
        }
    }

    private static void SelectVariable(ComboBox comboBox, string columnName)
    {
        if (string.IsNullOrWhiteSpace(columnName))
        {
            comboBox.SelectedIndex = comboBox.Items.Count > 0 ? 0 : -1;
            return;
        }

        var index = comboBox.FindStringExact(columnName);
        comboBox.SelectedIndex = index >= 0 ? index : (comboBox.Items.Count > 0 ? 0 : -1);
    }

    private void AddExplorerDirectory(string directoryPath, int depth, bool isRoot = false)
    {
        var displayName = isRoot
            ? Path.GetFileName(directoryPath).ToUpperInvariant()
            : Path.GetFileName(directoryPath);
        _fileListBox.Items.Add(new ExplorerItem(directoryPath, displayName, depth, IsDirectory: true, IsRoot: isRoot));

        if (!_expandedExplorerDirectories.Contains(directoryPath))
        {
            return;
        }

        foreach (var childDirectory in Directory.GetDirectories(directoryPath).OrderBy(Path.GetFileName, StringComparer.OrdinalIgnoreCase))
        {
            AddExplorerDirectory(childDirectory, depth + 1);
        }

        foreach (var childFile in Directory.GetFiles(directoryPath).OrderBy(Path.GetFileName, StringComparer.OrdinalIgnoreCase))
        {
            _fileListBox.Items.Add(new ExplorerItem(childFile, Path.GetFileName(childFile), depth + 1, IsDirectory: false, IsRoot: false));
        }
    }

    private void RestoreExplorerSelection(string? selectedPath)
    {
        if (string.IsNullOrWhiteSpace(selectedPath))
        {
            if (_fileListBox.Items.Count > 0)
            {
                _fileListBox.SelectedIndex = 0;
            }
            return;
        }

        for (var i = 0; i < _fileListBox.Items.Count; i++)
        {
            if (_fileListBox.Items[i] is ExplorerItem item &&
                item.FullPath.Equals(selectedPath, StringComparison.OrdinalIgnoreCase))
            {
                _fileListBox.SelectedIndex = i;
                return;
            }
        }

        if (_fileListBox.Items.Count > 0)
        {
            _fileListBox.SelectedIndex = 0;
        }
    }

    private void ToggleExplorerDirectory(string directoryPath)
    {
        if (!_expandedExplorerDirectories.Add(directoryPath))
        {
            _expandedExplorerDirectories.Remove(directoryPath);
        }

        PopulateFileExplorer();
    }

    private static string? ResolveExplorerRootPath()
    {
        var candidates = new List<string>
        {
            Path.Combine(Directory.GetCurrentDirectory(), "le_input_folder"),
            Path.Combine(AppContext.BaseDirectory, "le_input_folder")
        };

        for (var current = new DirectoryInfo(AppContext.BaseDirectory); current is not null; current = current.Parent)
        {
            candidates.Add(Path.Combine(current.FullName, "le_input_folder"));
        }

        return candidates
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault(Directory.Exists);
    }

    private static DataTable LoadCsvTable(string path)
    {
        var lines = File.ReadAllLines(path);
        if (lines.Length == 0)
        {
            throw new InvalidOperationException("Dataset is empty.");
        }

        var table = new DataTable();
        var headers = lines[0].Split(',');
        foreach (var header in headers)
        {
            table.Columns.Add(header.Trim());
        }

        foreach (var line in lines.Skip(1))
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            var values = line.Split(',');
            var row = table.NewRow();
            for (var i = 0; i < table.Columns.Count; i++)
            {
                row[i] = i < values.Length ? values[i].Trim() : string.Empty;
            }

            table.Rows.Add(row);
        }

        return table;
    }

    private void RenderGraphsWithPython()
    {
        if (_activeDatasetPath is null)
        {
            _graphStatusLabel.Text = "No dataset loaded.";
            return;
        }

        _graphHostPanel.Controls.Clear();
        var xVariable = _xVariableInput.SelectedItem?.ToString() ?? string.Empty;
        var yVariable = _yVariableInput.SelectedItem?.ToString() ?? string.Empty;

        try
        {
            var generated = GenerateGraphsViaPython(_activeDatasetPath, xVariable, yVariable);
            if (generated.Count == 0)
            {
                _graphStatusLabel.Text = "No chartable columns found.";
                _graphHostPanel.Controls.Add(_graphStatusLabel);
                return;
            }

            var tabs = new TabControl { Dock = DockStyle.Fill };
            foreach (var chart in generated)
            {
                var tab = new TabPage(chart.Title)
                {
                    BackColor = Color.FromArgb(37, 37, 38),
                    ForeColor = Color.Gainsboro
                };
                tab.Controls.Add(BuildImageChartViewer(chart.ImagePath));
                tabs.TabPages.Add(tab);
            }
            _graphHostPanel.Controls.Add(tabs);
        }
        catch (Exception ex)
        {
            _graphStatusLabel.Text = $"Graph generation failed: {ex.Message}";
            _graphHostPanel.Controls.Add(_graphStatusLabel);
        }
    }

    private static Control BuildImageChartViewer(string imagePath)
    {
        using var fs = File.OpenRead(imagePath);
        using var loaded = Image.FromStream(fs);
        var bitmap = new Bitmap(loaded);

        return new PictureBox
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(30, 30, 30),
            SizeMode = PictureBoxSizeMode.Zoom,
            Image = bitmap
        };
    }

    private static List<GeneratedChart> GenerateGraphsViaPython(string datasetPath, string xAxisColumn, string yAxisColumn)
    {
        var scriptPath = Path.Combine(AppContext.BaseDirectory, "Assets", "generate_graphs.py");
        if (!File.Exists(scriptPath))
        {
            throw new FileNotFoundException("Missing graph script.", scriptPath);
        }

        var outputDir = Path.Combine(Path.GetTempPath(), "GauntletGraphs", Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(outputDir);
        var manifestPath = Path.Combine(outputDir, "manifest.tsv");

        var args = new StringBuilder();
        args.Append('"').Append(scriptPath).Append('"');
        args.Append(" --input ").Append('"').Append(datasetPath).Append('"');
        args.Append(" --output ").Append('"').Append(outputDir).Append('"');
        args.Append(" --manifest ").Append('"').Append(manifestPath).Append('"');
        if (!string.IsNullOrWhiteSpace(xAxisColumn))
        {
            args.Append(" --xcol ").Append('"').Append(xAxisColumn).Append('"');
        }
        if (!string.IsNullOrWhiteSpace(yAxisColumn))
        {
            args.Append(" --ycol ").Append('"').Append(yAxisColumn).Append('"');
        }

        var run = TryRunPython("python", args.ToString());
        if (!run.Success)
        {
            run = TryRunPython("py", $"-3 {args}");
        }
        if (!run.Success)
        {
            throw new InvalidOperationException($"Python failed: {run.Error}");
        }

        if (!File.Exists(manifestPath))
        {
            throw new InvalidOperationException("Graph manifest was not produced.");
        }

        var charts = new List<GeneratedChart>();
        foreach (var line in File.ReadAllLines(manifestPath))
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            var parts = line.Split('\t');
            if (parts.Length < 2 || !File.Exists(parts[1]))
            {
                continue;
            }

            charts.Add(new GeneratedChart(parts[0], parts[1]));
        }

        return charts;
    }

    private static (bool Success, string Error) TryRunPython(string executable, string arguments)
    {
        var process = new Process
        {
            StartInfo = new ProcessStartInfo
            {
                FileName = executable,
                Arguments = arguments,
                CreateNoWindow = true,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true
            }
        };

        try
        {
            process.Start();
            var stdout = process.StandardOutput.ReadToEnd();
            var stderr = process.StandardError.ReadToEnd();
            process.WaitForExit();
            if (process.ExitCode == 0)
            {
                return (true, string.Empty);
            }

            var combined = string.IsNullOrWhiteSpace(stderr) ? stdout : stderr;
            return (false, combined.Trim());
        }
        catch (Exception ex)
        {
            return (false, ex.Message);
        }
    }

    private static void DrawFileGlyph(Graphics graphics, int x, int y, Color color)
    {
        using var pen = new Pen(color);
        var rect = new Rectangle(x, y, 10, 12);
        graphics.DrawRectangle(pen, rect);
        graphics.DrawLine(pen, rect.Right - 4, rect.Top, rect.Right, rect.Top + 4);
        graphics.DrawLine(pen, rect.Right - 4, rect.Top, rect.Right - 4, rect.Top + 4);
        graphics.DrawLine(pen, rect.Right - 4, rect.Top + 4, rect.Right, rect.Top + 4);
    }

    private static GraphicsPath CreateExplorerRoundedRectPath(Rectangle bounds, int radius)
    {
        var path = new GraphicsPath();
        var diameter = Math.Min(Math.Min(bounds.Width, bounds.Height), radius * 2);
        if (diameter <= 0)
        {
            path.AddRectangle(bounds);
            return path;
        }

        path.AddArc(bounds.X, bounds.Y, diameter, diameter, 180, 90);
        path.AddArc(bounds.Right - diameter, bounds.Y, diameter, diameter, 270, 90);
        path.AddArc(bounds.Right - diameter, bounds.Bottom - diameter, diameter, diameter, 0, 90);
        path.AddArc(bounds.X, bounds.Bottom - diameter, diameter, diameter, 90, 90);
        path.CloseFigure();
        return path;
    }

    private sealed record GeneratedChart(string Title, string ImagePath);

    private sealed record ExplorerItem(string FullPath, string DisplayName, int Depth, bool IsDirectory, bool IsRoot, bool IsPlaceholder = false)
    {
        public static ExplorerItem Placeholder(string text) => new(string.Empty, text, 0, IsDirectory: false, IsRoot: false, IsPlaceholder: true);
    }

    private sealed class DarkVScrollBar : Control
    {
        private const int ArrowHeight = 14;
        private int _maximum;
        private int _value;
        private bool _dragging;
        private int _dragOffset;

        public event Action<int>? ValueChanged;

        public int Maximum
        {
            get => _maximum;
            set
            {
                _maximum = Math.Max(0, value);
                Value = Math.Min(Value, _maximum);
                Invalidate();
            }
        }

        public int Value
        {
            get => _value;
            set
            {
                var clamped = Math.Max(0, Math.Min(value, Maximum));
                if (_value == clamped)
                {
                    return;
                }

                _value = clamped;
                Invalidate();
                ValueChanged?.Invoke(_value);
            }
        }

        public DarkVScrollBar()
        {
            SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer, true);
            BackColor = Color.FromArgb(30, 30, 30);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(BackColor);

            using var thumbBrush = new SolidBrush(Color.FromArgb(44, 47, 54));
            using var arrowBrush = new SolidBrush(Color.FromArgb(58, 58, 58));

            var trackRect = GetTrackRect();
            var thumb = GetThumbRect(trackRect);
            using (var thumbPath = CreateRoundedRectPath(thumb, 4))
            {
                g.FillPath(thumbBrush, thumbPath);
            }

            var up = new Point[]
            {
                new(Width / 2, 4),
                new(Width / 2 - 4, ArrowHeight - 4),
                new(Width / 2 + 4, ArrowHeight - 4)
            };
            var downBase = Height - ArrowHeight;
            var down = new Point[]
            {
                new(Width / 2 - 4, downBase + 4),
                new(Width / 2 + 4, downBase + 4),
                new(Width / 2, Height - 4)
            };
            g.FillPolygon(arrowBrush, up);
            g.FillPolygon(arrowBrush, down);
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            base.OnMouseDown(e);
            var track = GetTrackRect();
            var thumb = GetThumbRect(track);

            if (e.Y < ArrowHeight)
            {
                Value -= 1;
                return;
            }

            if (e.Y > Height - ArrowHeight)
            {
                Value += 1;
                return;
            }

            if (thumb.Contains(e.Location))
            {
                _dragging = true;
                _dragOffset = e.Y - thumb.Y;
                return;
            }

            if (e.Y < thumb.Y)
            {
                Value = Math.Max(0, Value - 5);
            }
            else if (e.Y > thumb.Bottom)
            {
                Value = Math.Min(Maximum, Value + 5);
            }
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            base.OnMouseMove(e);
            if (!_dragging || Maximum <= 0)
            {
                return;
            }

            var track = GetTrackRect();
            var thumb = GetThumbRect(track);
            var newThumbY = Math.Max(track.Top, Math.Min(e.Y - _dragOffset, track.Bottom - thumb.Height));
            var ratio = (double)(newThumbY - track.Top) / Math.Max(1, track.Height - thumb.Height);
            Value = (int)Math.Round(ratio * Maximum);
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            base.OnMouseUp(e);
            _dragging = false;
        }

        private Rectangle GetTrackRect()
        {
            return new Rectangle(0, ArrowHeight, Width, Math.Max(1, Height - (ArrowHeight * 2)));
        }

        private Rectangle GetThumbRect(Rectangle track)
        {
            var thumbHeight = Math.Max(34, track.Height / 4);
            var maxTravel = Math.Max(1, track.Height - thumbHeight);
            var y = track.Top + (Maximum == 0 ? 0 : (int)Math.Round((double)Value / Maximum * maxTravel));
            return new Rectangle(2, y, Math.Max(6, Width - 4), thumbHeight);
        }

        public static GraphicsPath CreateRoundedRectPath(Rectangle bounds, int radius)
        {
            var path = new GraphicsPath();
            var diameter = Math.Min(Math.Min(bounds.Width, bounds.Height), radius * 2);
            if (diameter <= 0)
            {
                path.AddRectangle(bounds);
                return path;
            }

            path.AddArc(bounds.X, bounds.Y, diameter, diameter, 180, 90);
            path.AddArc(bounds.Right - diameter, bounds.Y, diameter, diameter, 270, 90);
            path.AddArc(bounds.Right - diameter, bounds.Bottom - diameter, diameter, diameter, 0, 90);
            path.AddArc(bounds.X, bounds.Bottom - diameter, diameter, diameter, 90, 90);
            path.CloseFigure();
            return path;
        }
    }

    private sealed class DarkHScrollBar : Control
    {
        private const int ArrowWidth = 14;
        private int _maximum;
        private int _value;
        private bool _dragging;
        private int _dragOffset;

        public event Action<int>? ValueChanged;

        public int Maximum
        {
            get => _maximum;
            set
            {
                _maximum = Math.Max(0, value);
                Value = Math.Min(Value, _maximum);
                Invalidate();
            }
        }

        public int Value
        {
            get => _value;
            set
            {
                var clamped = Math.Max(0, Math.Min(value, Maximum));
                if (_value == clamped)
                {
                    return;
                }

                _value = clamped;
                Invalidate();
                ValueChanged?.Invoke(_value);
            }
        }

        public DarkHScrollBar()
        {
            SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer, true);
            BackColor = Color.FromArgb(30, 30, 30);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(BackColor);

            using var thumbBrush = new SolidBrush(Color.FromArgb(44, 47, 54));
            using var arrowBrush = new SolidBrush(Color.FromArgb(58, 58, 58));

            var trackRect = GetTrackRect();
            var thumb = GetThumbRect(trackRect);
            using (var thumbPath = DarkVScrollBar.CreateRoundedRectPath(thumb, 4))
            {
                g.FillPath(thumbBrush, thumbPath);
            }

            var left = new Point[]
            {
                new(4, Height / 2),
                new(ArrowWidth - 4, Height / 2 - 4),
                new(ArrowWidth - 4, Height / 2 + 4)
            };
            var rightBase = Width - ArrowWidth;
            var right = new Point[]
            {
                new(rightBase + 4, Height / 2 - 4),
                new(rightBase + 4, Height / 2 + 4),
                new(Width - 4, Height / 2)
            };
            g.FillPolygon(arrowBrush, left);
            g.FillPolygon(arrowBrush, right);
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            base.OnMouseDown(e);
            var track = GetTrackRect();
            var thumb = GetThumbRect(track);

            if (e.X < ArrowWidth)
            {
                Value -= 16;
                return;
            }

            if (e.X > Width - ArrowWidth)
            {
                Value += 16;
                return;
            }

            if (thumb.Contains(e.Location))
            {
                _dragging = true;
                _dragOffset = e.X - thumb.X;
                return;
            }

            if (e.X < thumb.X)
            {
                Value = Math.Max(0, Value - 48);
            }
            else if (e.X > thumb.Right)
            {
                Value = Math.Min(Maximum, Value + 48);
            }
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            base.OnMouseMove(e);
            if (!_dragging || Maximum <= 0)
            {
                return;
            }

            var track = GetTrackRect();
            var thumb = GetThumbRect(track);
            var newThumbX = Math.Max(track.Left, Math.Min(e.X - _dragOffset, track.Right - thumb.Width));
            var ratio = (double)(newThumbX - track.Left) / Math.Max(1, track.Width - thumb.Width);
            Value = (int)Math.Round(ratio * Maximum);
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            base.OnMouseUp(e);
            _dragging = false;
        }

        private Rectangle GetTrackRect()
        {
            return new Rectangle(ArrowWidth, 0, Math.Max(1, Width - (ArrowWidth * 2)), Height);
        }

        private Rectangle GetThumbRect(Rectangle track)
        {
            var thumbWidth = Math.Max(34, track.Width / 4);
            var maxTravel = Math.Max(1, track.Width - thumbWidth);
            var x = track.Left + (Maximum == 0 ? 0 : (int)Math.Round((double)Value / Maximum * maxTravel));
            return new Rectangle(x, 2, thumbWidth, Math.Max(6, Height - 4));
        }
    }

    private sealed class FileListBox : ListBox
    {
        private const int SbVert = 1;

        [System.Runtime.InteropServices.DllImport("user32.dll")]
        private static extern bool ShowScrollBar(IntPtr hWnd, int wBar, bool bShow);

        protected override void OnHandleCreated(EventArgs e)
        {
            base.OnHandleCreated(e);
            ShowScrollBar(Handle, SbVert, false);
        }

        protected override void WndProc(ref Message m)
        {
            base.WndProc(ref m);
            if (IsHandleCreated)
            {
                ShowScrollBar(Handle, SbVert, false);
            }
        }
    }
}
