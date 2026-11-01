// Category: Type Errors (Success Case)
// Expected Result: Handle truncation explicitly or use rounding

#include <iostream>
#include <cmath>

int main() {
    double price = 99.99;
    
    // SUCCESS: Explicitly rounded or handled truncation
    int dollars = (int)std::floor(price);
    
    std::cout << "Original price: " << price << std::endl;
    std::cout << "Dollars (truncated/floored): " << dollars << std::endl;
    
    return 0;
}
