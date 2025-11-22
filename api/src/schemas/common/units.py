"""Common models/units."""

from typing import Annotated

from pydantic import Field

KbtuPerFt2 = Annotated[float, Field(..., description="**Unit:** kBTU/ft2", title="kBTU/ft2")]
LbsCO2ePerFt2 = Annotated[float, Field(..., description="**Unit:** lbsCO2e/ft2", title="lbsCO2e/ft2")]
Percentage = Annotated[
    float, Field(..., description="Percentage value as a decimal fraction.\n1.0 = 100%, 0.01 = 1%", title="Percentage")
]
