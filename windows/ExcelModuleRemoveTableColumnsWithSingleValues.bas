Attribute VB_Name = "ModuleRemoveTableColumnsWithSingleValues"
Sub RemoveTableColumnsWithSingleValues()
    Dim ws As Worksheet
    Dim table As ListObject
    Dim col As ListColumn
    Dim cell As Range
    Dim firstValue As Variant
    Dim identical As Boolean
    Dim lastCol As Long
    Dim i As Long

    Set ws = ActiveSheet
    Set table = ws.ListObjects(1)
    
    For i = table.ListColumns.Count To 1 Step -1
        Set col = table.ListColumns(i)
        firstValue = col.DataBodyRange.Cells(1, 1).Value
        identical = True

        For Each cell In col.DataBodyRange.Cells
            If cell.Value <> firstValue Then
                identical = False
                Exit For
            End If
        Next cell

        If identical Then
            col.Delete
        End If
    Next i
End Sub
