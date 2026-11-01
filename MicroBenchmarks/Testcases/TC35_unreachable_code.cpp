// Category: Logic Errors
// Error: Dead code / unreachable code

#include <iostream>

int getValue() {
    return 42;
    std::cout << "This will never print" << std::endl;  // ERROR: Unreachable code
    return 0;
}

int main() {
    std::cout << getValue() << std::endl;
    return 0;
}
