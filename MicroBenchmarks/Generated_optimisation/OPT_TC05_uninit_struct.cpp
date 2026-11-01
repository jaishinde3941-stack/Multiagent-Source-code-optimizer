// Category: Uninitialized Variables
// Error: Using uninitialized struct member

#include <iostream>

struct Point {
    int x = 0;
    int y = 0;
};

int main() {
    Point p;
    
    int distance = p.x * p.x + p.y * p.y;  // ERROR: p.x and p.y are uninitialized
    std::cout << "Distance squared: " << distance << std::endl;
    
    return 0;
}
