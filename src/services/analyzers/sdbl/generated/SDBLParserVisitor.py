# Generated from SDBLParser.g4 by ANTLR 4.13.1
from antlr4 import *
if "." in __name__:
    from .SDBLParser import SDBLParser
else:
    from SDBLParser import SDBLParser

# This class defines a complete generic visitor for a parse tree produced by SDBLParser.

class SDBLParserVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by SDBLParser#queryPackage.
    def visitQueryPackage(self, ctx:SDBLParser.QueryPackageContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#queries.
    def visitQueries(self, ctx:SDBLParser.QueriesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#dropTableQuery.
    def visitDropTableQuery(self, ctx:SDBLParser.DropTableQueryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#selectQuery.
    def visitSelectQuery(self, ctx:SDBLParser.SelectQueryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#subquery.
    def visitSubquery(self, ctx:SDBLParser.SubqueryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#union.
    def visitUnion(self, ctx:SDBLParser.UnionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#query.
    def visitQuery(self, ctx:SDBLParser.QueryContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#limitations.
    def visitLimitations(self, ctx:SDBLParser.LimitationsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#top.
    def visitTop(self, ctx:SDBLParser.TopContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#selectedFields.
    def visitSelectedFields(self, ctx:SDBLParser.SelectedFieldsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#selectedField.
    def visitSelectedField(self, ctx:SDBLParser.SelectedFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#asteriskField.
    def visitAsteriskField(self, ctx:SDBLParser.AsteriskFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#expressionField.
    def visitExpressionField(self, ctx:SDBLParser.ExpressionFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#columnField.
    def visitColumnField(self, ctx:SDBLParser.ColumnFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#emptyTableField.
    def visitEmptyTableField(self, ctx:SDBLParser.EmptyTableFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#emptyTableColumns.
    def visitEmptyTableColumns(self, ctx:SDBLParser.EmptyTableColumnsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#inlineTableField.
    def visitInlineTableField(self, ctx:SDBLParser.InlineTableFieldContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#recordAutoNumberFunction.
    def visitRecordAutoNumberFunction(self, ctx:SDBLParser.RecordAutoNumberFunctionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#indexingItem.
    def visitIndexingItem(self, ctx:SDBLParser.IndexingItemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#indexingSet.
    def visitIndexingSet(self, ctx:SDBLParser.IndexingSetContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#orderBy.
    def visitOrderBy(self, ctx:SDBLParser.OrderByContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#ordersByExpression.
    def visitOrdersByExpression(self, ctx:SDBLParser.OrdersByExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#totalBy.
    def visitTotalBy(self, ctx:SDBLParser.TotalByContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#totalsGroup.
    def visitTotalsGroup(self, ctx:SDBLParser.TotalsGroupContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#periodic.
    def visitPeriodic(self, ctx:SDBLParser.PeriodicContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#column.
    def visitColumn(self, ctx:SDBLParser.ColumnContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#expression.
    def visitExpression(self, ctx:SDBLParser.ExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#primitiveExpression.
    def visitPrimitiveExpression(self, ctx:SDBLParser.PrimitiveExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#caseExpression.
    def visitCaseExpression(self, ctx:SDBLParser.CaseExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#caseBranch.
    def visitCaseBranch(self, ctx:SDBLParser.CaseBranchContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#bracketExpression.
    def visitBracketExpression(self, ctx:SDBLParser.BracketExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#unaryExpression.
    def visitUnaryExpression(self, ctx:SDBLParser.UnaryExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#functionCall.
    def visitFunctionCall(self, ctx:SDBLParser.FunctionCallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#builtInFunctions.
    def visitBuiltInFunctions(self, ctx:SDBLParser.BuiltInFunctionsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#aggregateFunctions.
    def visitAggregateFunctions(self, ctx:SDBLParser.AggregateFunctionsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#valueFunction.
    def visitValueFunction(self, ctx:SDBLParser.ValueFunctionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#castFunction.
    def visitCastFunction(self, ctx:SDBLParser.CastFunctionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#logicalExpression.
    def visitLogicalExpression(self, ctx:SDBLParser.LogicalExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#predicate.
    def visitPredicate(self, ctx:SDBLParser.PredicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#likePredicate.
    def visitLikePredicate(self, ctx:SDBLParser.LikePredicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#isNullPredicate.
    def visitIsNullPredicate(self, ctx:SDBLParser.IsNullPredicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#comparePredicate.
    def visitComparePredicate(self, ctx:SDBLParser.ComparePredicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#betweenPredicate.
    def visitBetweenPredicate(self, ctx:SDBLParser.BetweenPredicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#inPredicate.
    def visitInPredicate(self, ctx:SDBLParser.InPredicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#refsPredicate.
    def visitRefsPredicate(self, ctx:SDBLParser.RefsPredicateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#expressionList.
    def visitExpressionList(self, ctx:SDBLParser.ExpressionListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#expressionListItem.
    def visitExpressionListItem(self, ctx:SDBLParser.ExpressionListItemContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#dataSources.
    def visitDataSources(self, ctx:SDBLParser.DataSourcesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#dataSource.
    def visitDataSource(self, ctx:SDBLParser.DataSourceContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#table.
    def visitTable(self, ctx:SDBLParser.TableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#virtualTable.
    def visitVirtualTable(self, ctx:SDBLParser.VirtualTableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#virtualTableParameter.
    def visitVirtualTableParameter(self, ctx:SDBLParser.VirtualTableParameterContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#parameterTable.
    def visitParameterTable(self, ctx:SDBLParser.ParameterTableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#externalDataSourceTable.
    def visitExternalDataSourceTable(self, ctx:SDBLParser.ExternalDataSourceTableContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#joinPart.
    def visitJoinPart(self, ctx:SDBLParser.JoinPartContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#rightJoin.
    def visitRightJoin(self, ctx:SDBLParser.RightJoinContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#leftJoin.
    def visitLeftJoin(self, ctx:SDBLParser.LeftJoinContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#fullJoin.
    def visitFullJoin(self, ctx:SDBLParser.FullJoinContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#innerJoin.
    def visitInnerJoin(self, ctx:SDBLParser.InnerJoinContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#alias.
    def visitAlias(self, ctx:SDBLParser.AliasContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#datePart.
    def visitDatePart(self, ctx:SDBLParser.DatePartContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#multiString.
    def visitMultiString(self, ctx:SDBLParser.MultiStringContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#sign.
    def visitSign(self, ctx:SDBLParser.SignContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#identifier.
    def visitIdentifier(self, ctx:SDBLParser.IdentifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#temporaryTableIdentifier.
    def visitTemporaryTableIdentifier(self, ctx:SDBLParser.TemporaryTableIdentifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#parameter.
    def visitParameter(self, ctx:SDBLParser.ParameterContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SDBLParser#mdo.
    def visitMdo(self, ctx:SDBLParser.MdoContext):
        return self.visitChildren(ctx)



del SDBLParser