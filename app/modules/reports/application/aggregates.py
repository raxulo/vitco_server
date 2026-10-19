from sqlalchemy import func


class Aggregates:

    @staticmethod
    def quantity(column):
        return func.coalesce(
            func.sum(column),
            0,
        )

    @staticmethod
    def amount(column):
        return func.coalesce(
            func.sum(column),
            0,
        )

    @staticmethod
    def count(column):
        return func.coalesce(
            func.count(column),
            0,
        )

    @staticmethod
    def weighted_sum(
        quantity,
        value,
    ):
        return func.coalesce(
            func.sum(quantity * value),
            0,
        )

    @staticmethod
    def weighted_average(
        quantity,
        value,
    ):
        return (
            func.sum(quantity * value)
            /
            func.nullif(
                func.sum(quantity),
                0,
            )
        )